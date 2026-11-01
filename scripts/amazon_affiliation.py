"""Amazon Associates FR report observations, never inferred individual sales/losses."""
import base64
import binascii
import stat
import zipfile
import csv
import hashlib
import io
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

LIMIT = 1024 * 1024
FIELDS = ('date','tracking_id','asin','title','provider_status','transaction_id','orders','ordered_items','shipped_items','commission_cents','payment_cents')
METRICS = {'orders':('orders','ordered_items'), 'earnings':('shipped_items','commission_cents'), 'payments':('payment_cents',)}



VIEWS = {'legacy', 'category', 'linked_product', 'tracking_id', 'daily_trends'}

def inspect_archive(data):
    """Read bounded text members in memory. Never extract paths or import totals."""
    encoded=data.get('archive')
    if not isinstance(encoded,str) or len(encoded)>((LIMIT+2)//3)*4:
        raise ValueError('Archive ZIP limitée à 1 Mo.')
    try:
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>LIMIT: raise ValueError()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members=archive.infolist()
            if not 1<=len(members)<=16: raise ValueError()
            total=0;files=[];names=set()
            for entry in members:
                name=entry.filename
                if name.startswith(('/', '\\')) or '\\' in name or ':' in name or '..' in name.split('/') or stat.S_ISLNK(entry.external_attr>>16): raise ValueError()
                if entry.is_dir(): continue
                if name in names or entry.flag_bits&1 or not name.lower().endswith(('.csv','.txt')): raise ValueError()
                names.add(name);total+=entry.file_size
                if total>LIMIT or entry.file_size>LIMIT or entry.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED): raise ValueError()
                with archive.open(entry) as stream: payload=stream.read(LIMIT+1)
                if len(payload)!=entry.file_size: raise ValueError()
                text=payload.decode('utf-8-sig')
                if '\x00' in text: raise ValueError()
                files.append({'name':name,'csv':text})
            if not files: raise ValueError()
            return {'files':files,'imported':False}
    except (ValueError,binascii.Error,zipfile.BadZipFile,RuntimeError,NotImplementedError,OSError,UnicodeError):
        raise ValueError('ZIP invalide : CSV/TXT UTF-8 uniquement, 16 entrées et 1 Mo décompressé maximum, sans chiffrement ni chemins dangereux.') from None


def inspect_csv(data):
    text=data.get('csv')
    if not isinstance(text,str) or not text.strip() or len(text.encode('utf-8'))>LIMIT:
        raise ValueError('Rapport CSV UTF-8 requis, limité à 1 Mo.')
    try:
        offset=int(data.get('header_row',1))-1
        if not 0<=offset<=100: raise ValueError()
        lines=text.lstrip('\ufeff').splitlines(keepends=True)[offset:]
        dialect=csv.Sniffer().sniff(''.join(lines[:10]),delimiters=',;\t')
        reader=csv.reader(io.StringIO(''.join(lines)),dialect)
        headers=next(reader); rows=list(reader)
        if not headers or len(headers)>100 or len(set(headers))!=len(headers) or any(not h.strip() for h in headers): raise ValueError()
        rows=[r for r in rows if any(c.strip() for c in r)]
        if len(rows)>10000 or any(len(r)!=len(headers) for r in rows): raise ValueError()
    except (ValueError,StopIteration,csv.Error):
        raise ValueError('En-tête ou lignes CSV invalides. Indiquez la ligne d’en-tête ; retirez les totaux et pieds de page.') from None
    return headers,rows


def normalize(data):
    headers,rows=inspect_csv(data)
    view=data.get('view','legacy')
    if view not in VIEWS: raise ValueError('Vue Amazon inconnue.')
    kind=data.get('kind'); mapping=data.get('mapping',{})
    if kind not in METRICS or not isinstance(mapping,dict) or set(mapping)-set(FIELDS): raise ValueError('Type ou colonnes invalides.')
    if not mapping.get('date') or not any(mapping.get(k) for k in METRICS[kind]): raise ValueError('Associez la date et au moins un indicateur du type de rapport choisi.')
    if any(v not in headers for v in mapping.values() if v) or len([v for v in mapping.values() if v])!=len(set(v for v in mapping.values() if v)): raise ValueError('Correspondance de colonnes invalide ou dupliquée.')
    if any(mapping.get(k) for k in set(FIELDS[6:])-set(METRICS[kind])): raise ValueError('Séparez les rapports Commandes, Rémunérations et Paiements.')
    try:
        start=date.fromisoformat(data['start']).isoformat();end=date.fromisoformat(data['end']).isoformat()
        if start>end: raise ValueError()
    except (ValueError,KeyError,TypeError): raise ValueError('Période du rapport invalide.') from None
    scope=data.get('scope','').strip()
    if not re.fullmatch(r'(all|[A-Za-z0-9_-]{1,100})',scope): raise ValueError('Indiquez all pour tous les Tracking IDs, ou le Tracking ID exact.')
    decimal=data.get('decimal','comma')
    if decimal not in {'comma','dot'}: raise ValueError('Séparateur décimal invalide.')
    result=[]
    for row in rows:
        item={k:(row[headers.index(mapping[k])].strip() if mapping.get(k) else '') for k in FIELDS}
        try:
            day=date.fromisoformat(item['date']) if re.fullmatch(r'\d{4}-\d{2}-\d{2}',item['date']) else datetime.strptime(item['date'],'%d/%m/%Y').date()
            item['date']=day.isoformat()
            if not start<=item['date']<=end: raise ValueError()
            for key in FIELDS[6:]:
                raw=item[key].replace('\u00a0','').replace('\u202f','').replace(' ','')
                if not raw: item[key]=None;continue
                if decimal=='comma': raw=raw.replace(',','.')
                if not re.fullmatch(r'-?\d+(\.\d+)?',raw): raise ValueError()
                value=Decimal(raw)*(100 if key.endswith('_cents') else 1)
                if not value.is_finite() or value!=value.to_integral_value() or abs(value)>10**14: raise ValueError()
                item[key]=int(value)
            if scope!='all':
                if item['tracking_id'] and item['tracking_id']!=scope: raise ValueError()
                item['tracking_id']=scope
            if any(len(item[k])>500 for k in ('tracking_id','asin','title','provider_status','transaction_id')): raise ValueError()
        except (ValueError,InvalidOperation): raise ValueError('Date, quantité, montant EUR ou Tracking ID invalide. Aucun import effectué.') from None
        result.append(item)
    return {'version':1,**({'view':view} if view!='legacy' else {}),'kind':kind,'start':start,'end':end,'scope':scope,'currency':'EUR','rows':result}


def active_reports(db,identity):
    latest={}
    for row in db.execute('SELECT * FROM aff_snapshots WHERE account_id=? ORDER BY id',(identity,)):
        value=json.loads(row['summary']).get('amazon')
        if value:
            latest[(value['kind'],value['start'],value['end'],value['scope'])]={'id':row['id'],'observed_at':row['observed_at'],**value}
    return list(latest.values())


def validate_saved(value):
    if not isinstance(value,dict) or set(value)-{'view'}!={'version','kind','start','end','scope','currency','rows','digest'} or value['version']!=1 or value['currency']!='EUR':raise ValueError('Rapport Amazon sauvegardé invalide.')
    if value.get('view','legacy') not in VIEWS: raise ValueError('Vue Amazon sauvegardée invalide.')
    if value['kind'] not in METRICS or not isinstance(value['rows'],list) or len(value['rows'])>10000:raise ValueError('Rapport Amazon sauvegardé invalide.')
    if date.fromisoformat(value['start'])>date.fromisoformat(value['end']) or not re.fullmatch(r'(all|[A-Za-z0-9_-]{1,100})',value['scope']):raise ValueError('Périmètre Amazon invalide.')
    for row in value['rows']:
        if not isinstance(row,dict) or set(row)!=set(FIELDS):raise ValueError('Ligne Amazon invalide.')
        if not value['start']<=date.fromisoformat(row['date']).isoformat()<=value['end']:raise ValueError('Date Amazon invalide.')
        for key in FIELDS[1:6]:
            if not isinstance(row[key],str) or len(row[key])>500:raise ValueError('Texte Amazon invalide.')
        for key in FIELDS[6:]:
            if row[key] is not None and (key not in METRICS[value['kind']] or type(row[key]) is not int or abs(row[key])>10**14):raise ValueError('Indicateur Amazon invalide.')
    original={k:v for k,v in value.items() if k!='digest'}
    if hashlib.sha256(json.dumps(original,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=value['digest']:raise ValueError('Empreinte Amazon invalide.')


def ingest(db,identity,data,observed):
    if data.get('confirmed') is not True: raise ValueError('Confirmez la période, les colonnes et l’absence de lignes de total.')
    value=normalize(data)
    canonical=json.dumps(value,sort_keys=True,ensure_ascii=False)
    digest=hashlib.sha256(canonical.encode()).hexdigest()
    for previous in active_reports(db,identity):
        same=all(previous[k]==value[k] for k in ('kind','start','end','scope'))
        if same and previous.get('view','legacy')!=value.get('view','legacy'):
            raise ValueError('Une autre vue couvre déjà ces indicateurs et cette période. Ne cumulez pas Catégories, Produits liés, Tracking IDs et Tendances quotidiennes ; conservez la même vue de référence.')
        if same and previous.get('digest')==digest:return {'ok':True,'duplicate':True,'rows':len(value['rows'])}
        overlap=previous['start']<=value['end'] and value['start']<=previous['end']
        shared=previous['scope']==value['scope'] or 'all' in (previous['scope'],value['scope'])
        if previous['kind']==value['kind'] and overlap and shared and not same:
            raise ValueError('Périodes/Tracking IDs chevauchants : import refusé pour éviter un double comptage. Réimportez le même périmètre pour le corriger.')
    value['digest']=digest
    db.execute('INSERT INTO aff_snapshots(account_id,observed_at,summary,row_count,pages,source) VALUES(?,?,?,?,1,?)',
               (identity,observed,json.dumps({'amazon':value}),len(value['rows']),'amazon-csv'))
    db.execute('UPDATE aff_accounts SET last_success=?,last_error=NULL WHERE id=?',(observed,identity))
    return {'ok':True,'duplicate':False,'rows':len(value['rows'])}


def report(db,identity,start='',end=''):
    reports=active_reports(db,identity);rows=[]
    for report in reports:
        rows.extend({**r,'kind':report['kind']} for r in report['rows'] if (not start or r['date']>=start) and (not end or r['date']<=end))
    totals={key:(sum(r[key] for r in rows if r[key] is not None) if any(r[key] is not None for r in rows) else None) for key in FIELDS[6:]}
    return {'totals':totals,'rows':rows,'reports':[{k:r[k] for k in ('id','kind','start','end','scope','observed_at')} for r in reports],
            'loss_tracking':False,'limitation':'Rapports agrégés ou limités dans le temps : aucune perte par transaction calculée.'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def credentials(identity):
    prefix='AMAZON_CREATORS_'+identity.upper()+'_'
    values=[os.environ.get(prefix+k,'') for k in ('CREDENTIAL_ID','CREDENTIAL_SECRET','VERSION')]
    if not all(values):raise ValueError('Identifiants Creators API absents côté serveur. Aucun secret ne doit être saisi dans LinKs.')
    if values[2] not in {'2.2','3.2'}:raise ValueError('Version EU attendue : 2.2 ou 3.2. Vérifiez les identifiants Amazon France.')
    return values


def read_json(url,body,headers):
    # Fixed Amazon endpoints only; no redirects, raw exception bodies or token logging.
    try:
        with build_opener(NoRedirect).open(Request(url,body,headers,method='POST'),timeout=25) as response:
            raw=response.read(LIMIT+1)
        if len(raw)>LIMIT:raise ValueError()
        return json.loads(raw)
    except Exception:raise ValueError('Accès Creators API impossible. Vérifiez les autorisations du compte et réessayez ; aucun secret ni réponse brute n’est affiché.') from None


def list_reports(identity):
    client,secret,version=credentials(identity)
    endpoint='https://api.amazon.co.uk/auth/o2/token' if version=='3.2' else 'https://creatorsapi.auth.eu-south-2.amazoncognito.com/oauth2/token'
    scope='creatorsapi::default' if version=='3.2' else 'creatorsapi/default'
    token=read_json(endpoint,urlencode({'grant_type':'client_credentials','client_id':client,'client_secret':secret,'scope':scope}).encode(),{'Content-Type':'application/x-www-form-urlencoded'}).get('access_token')
    if not isinstance(token,str) or not token:raise ValueError('Jeton Amazon indisponible.')
    authorization='Bearer '+token+(', Version 2.2' if version=='2.2' else '')
    headers={'Content-Type':'application/json','Authorization':authorization,'x-marketplace':'www.amazon.fr'}
    result=read_json('https://creatorsapi.amazon/reports/v1/listReports',b'',headers)
    reports=result.get('reports')
    if not isinstance(reports,list):raise ValueError('Liste de rapports Amazon non reconnue.')
    safe=[]
    for r in reports:
        if not isinstance(r,dict) or not isinstance(r.get('filename'),str) or len(r['filename'])>500:raise ValueError('Métadonnées Amazon non reconnues.')
        safe.append({k:r.get(k) for k in ('filename','reportType','lastModified','size')})
    return safe,headers


def retrieve_report(identity,filename,report_type):
    reports,headers=list_reports(identity)
    if not any(r['filename']==filename and r['reportType']==report_type for r in reports):raise ValueError('Rapport absent de la liste autorisée de ce compte.')
    body={'filename':filename}
    if report_type:body['reportType']=report_type
    result=read_json('https://creatorsapi.amazon/reports/v1/getReport',json.dumps(body).encode(),headers)
    url=result.get('url','');parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443) or not parsed.hostname or not parsed.hostname.endswith('.amazonaws.com') or not any(p=='s3' or p.startswith('s3-') for p in parsed.hostname.split('.')):
        raise ValueError('Destination du rapport non prise en charge. Utilisez le téléchargement manuel Amazon.')
    try:
        with build_opener(NoRedirect).open(Request(url),timeout=25) as response:raw=response.read(LIMIT+1)
        if len(raw)>LIMIT:raise ValueError()
        text=raw.decode('utf-8-sig')
        inspect_csv({'csv':text})
        return {'csv':text}
    except Exception:raise ValueError('Rapport non exploitable en CSV UTF-8 (1 Mo maximum). Utilisez un export CSV du portail.') from None
