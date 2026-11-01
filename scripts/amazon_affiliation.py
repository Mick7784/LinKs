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
FIELDS = ('date','tracking_id','asin','title','provider_status','transaction_id','orders','ordered_items','shipped_items','commission_cents','payment_cents','clicks')
METRICS = {'orders':('orders','ordered_items'), 'earnings':('shipped_items','commission_cents'), 'payments':('payment_cents',), 'performance':('clicks','ordered_items','shipped_items','commission_cents')}



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
        if not headers or len(headers)>100 or any(not h.strip() for h in headers): raise ValueError()
        original=headers[:]
        headers=[h if original.count(h)==1 else f'{h} [colonne {i+1}]' for i,h in enumerate(original)]
        if len(set(headers))!=len(headers): raise ValueError()
        rows=[r for r in rows if any(c.strip() for c in r)]
        if len(rows)>10000 or any(len(r)!=len(headers) for r in rows): raise ValueError()
    except (ValueError,StopIteration,csv.Error):
        raise ValueError('En-tête ou lignes CSV invalides. Indiquez la ligne d’en-tête ; retirez les totaux et pieds de page.') from None
    return headers,rows


def normalize(data):
    headers,rows=inspect_csv(data)
    view=data.get('view','legacy')
    if view not in VIEWS: raise ValueError('Vue Amazon inconnue.')
    contribution=data.get('contribution','totals')
    if contribution not in {'totals','detail'}: raise ValueError('Usage du rapport invalide.')
    kind=data.get('kind'); mapping=data.get('mapping',{})
    if kind not in METRICS or not isinstance(mapping,dict) or set(mapping)-set(FIELDS): raise ValueError('Type ou colonnes invalides.')
    if (not mapping.get('date') and data.get('single_day') is not True) or not any(mapping.get(k) for k in METRICS[kind]): raise ValueError('Associez la date et au moins un indicateur du type de rapport choisi.')
    if any(v not in headers for v in mapping.values() if v) or len([v for v in mapping.values() if v])!=len(set(v for v in mapping.values() if v)): raise ValueError('Correspondance de colonnes invalide ou dupliquée.')
    if any(mapping.get(k) for k in set(FIELDS[6:])-set(METRICS[kind])): raise ValueError('Séparez les rapports Commandes, Rémunérations et Paiements.')
    try:
        start=date.fromisoformat(data['start']).isoformat();end=date.fromisoformat(data['end']).isoformat()
        if start>end: raise ValueError()
    except (ValueError,KeyError,TypeError): raise ValueError('Période du rapport invalide.') from None
    scope=data.get('scope','').strip()
    if not re.fullmatch(r'(all|[A-Za-z0-9_-]{1,100})',scope): raise ValueError('Indiquez all pour tous les Tracking IDs, ou le Tracking ID exact.')
    if data.get('single_day') is True and start!=end: raise ValueError('Sans colonne Date, seule une période explicitement confirmée d’un jour est acceptée.')
    date_format=data.get('date_format','dmy')
    if date_format not in {'dmy','mdy'}: raise ValueError('Format de date invalide.')
    decimal=data.get('decimal','comma')
    if decimal not in {'comma','dot'}: raise ValueError('Séparateur décimal invalide.')
    result=[]
    for row in rows:
        item={k:(row[headers.index(mapping[k])].strip() if mapping.get(k) else '') for k in FIELDS}
        try:
            if not mapping.get('date') and data.get('single_day') is True: item['date']=start
            day=date.fromisoformat(item['date']) if re.fullmatch(r'\d{4}-\d{2}-\d{2}',item['date']) else datetime.strptime(item['date'],'%m-%d-%Y' if date_format=='mdy' else '%d/%m/%Y').date()
            item['date']=day.isoformat()
            if not start<=item['date']<=end: raise ValueError()
            for key in FIELDS[6:]:
                raw=item[key].replace('\u00a0','').replace('\u202f','').replace(' ','')
                if raw in {'','-'}: item[key]=None;continue
                if decimal=='comma': raw=raw.replace(',','.')
                if not re.fullmatch(r'-?\d+(\.\d+)?',raw): raise ValueError()
                value=Decimal(raw)*(100 if key.endswith('_cents') else 1)
                if key.endswith('_cents') and value.is_finite() and abs(value-value.to_integral_value())<=Decimal('0.00000001'): value=value.to_integral_value()
                if not value.is_finite() or value!=value.to_integral_value() or abs(value)>10**14: raise ValueError()
                item[key]=int(value)
            if scope!='all':
                if item['tracking_id'] and item['tracking_id']!=scope: raise ValueError()
                item['tracking_id']=scope
            if any(len(item[k])>500 for k in ('tracking_id','asin','title','provider_status','transaction_id')): raise ValueError()
        except (ValueError,InvalidOperation): raise ValueError('Date, quantité, montant EUR ou Tracking ID invalide. Aucun import effectué.') from None
        result.append(item)
    return {'version':1,**({'contribution':contribution} if contribution=='detail' else {}),**({'date_basis':'confirmed_single_day'} if not mapping.get('date') else {}),**({'view':view} if view!='legacy' else {}),'kind':kind,'start':start,'end':end,'scope':scope,'currency':'EUR','rows':result}


def active_reports(db,identity):
    latest={}
    for row in db.execute('SELECT * FROM aff_snapshots WHERE account_id=? ORDER BY id',(identity,)):
        value=json.loads(row['summary']).get('amazon')
        if value:
            latest[(value['kind'],value['start'],value['end'],value['scope'],value.get('view','legacy'),value.get('contribution','totals'))]={'id':row['id'],'observed_at':row['observed_at'],**value}
    return list(latest.values())


def validate_saved(value):
    if not isinstance(value,dict) or set(value)-{'view','date_basis','contribution'}!={'version','kind','start','end','scope','currency','rows','digest'} or value['version']!=1 or value['currency']!='EUR':raise ValueError('Rapport Amazon sauvegardé invalide.')
    if value.get('contribution','totals') not in {'totals','detail'}: raise ValueError('Usage sauvegardé invalide.')
    if 'date_basis' in value and (value['date_basis']!='confirmed_single_day' or value['start']!=value['end']): raise ValueError('Origine de date invalide.')
    if value.get('view','legacy') not in VIEWS: raise ValueError('Vue Amazon sauvegardée invalide.')
    if value['kind'] not in METRICS or not isinstance(value['rows'],list) or len(value['rows'])>10000:raise ValueError('Rapport Amazon sauvegardé invalide.')
    if date.fromisoformat(value['start'])>date.fromisoformat(value['end']) or not re.fullmatch(r'(all|[A-Za-z0-9_-]{1,100})',value['scope']):raise ValueError('Périmètre Amazon invalide.')
    for row in value['rows']:
        if not isinstance(row,dict) or set(row) not in (set(FIELDS),set(FIELDS)-{'clicks'}):raise ValueError('Ligne Amazon invalide.')
        if not value['start']<=date.fromisoformat(row['date']).isoformat()<=value['end']:raise ValueError('Date Amazon invalide.')
        for key in FIELDS[1:6]:
            if not isinstance(row[key],str) or len(row[key])>500:raise ValueError('Texte Amazon invalide.')
        for key in FIELDS[6:]:
            if row.get(key) is not None and (key not in METRICS[value['kind']] or type(row[key]) is not int or abs(row[key])>10**14):raise ValueError('Indicateur Amazon invalide.')
    original={k:v for k,v in value.items() if k!='digest'}
    if hashlib.sha256(json.dumps(original,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=value['digest']:raise ValueError('Empreinte Amazon invalide.')


def ingest(db,identity,data,observed):
    if data.get('confirmed') is not True: raise ValueError('Confirmez la période, les colonnes et l’absence de lignes de total.')
    value=normalize(data)
    canonical=json.dumps(value,sort_keys=True,ensure_ascii=False)
    digest=hashlib.sha256(canonical.encode()).hexdigest()
    for previous in active_reports(db,identity):
        same=all(previous[k]==value[k] for k in ('kind','start','end','scope'))
        same_view=previous.get('view','legacy')==value.get('view','legacy')
        same_usage=previous.get('contribution','totals')==value.get('contribution','totals')
        if same and same_view and same_usage and previous.get('digest')==digest:return {'ok':True,'duplicate':True,'rows':len(value['rows'])}
        overlap=previous['start']<=value['end'] and value['start']<=previous['end']
        shared=previous['scope']==value['scope'] or 'all' in (previous['scope'],value['scope'])
        financial=previous.get('contribution','totals')=='totals' and value.get('contribution','totals')=='totals'
        common=set(METRICS[previous['kind']]) & set(METRICS[value['kind']])
        if overlap and shared and common and (financial or (same_usage and same_view)):
            if not (same and same_view and same_usage):
                raise ValueError('Indicateurs et périodes chevauchants : utilisez une vue complémentaire pour éviter le double comptage. Une correction doit conserver la même vue et le même périmètre.')
    value['digest']=digest
    db.execute('INSERT INTO aff_snapshots(account_id,observed_at,summary,row_count,pages,source) VALUES(?,?,?,?,1,?)',
               (identity,observed,json.dumps({'amazon':value}),len(value['rows']),'amazon-csv'))
    db.execute('UPDATE aff_accounts SET last_success=?,last_error=NULL WHERE id=?',(observed,identity))
    return {'ok':True,'duplicate':False,'rows':len(value['rows'])}


def report(db,identity,start='',end=''):
    reports=active_reports(db,identity);rows=[];details=[];dated=[]
    for source in reports:
        selected=[{**r,'clicks':r.get('clicks'),'kind':source['kind'],'view':source.get('view','legacy')} for r in source['rows'] if (not start or r['date']>=start) and (not end or r['date']<=end)]
        if source.get('contribution','totals')=='totals':
            rows.extend(selected)
            if not source.get('date_basis'):dated.extend(selected)
        else:details.extend(selected)
    def totals(items):
        return {key:sum(r.get(key) or 0 for r in items) if any(r.get(key) is not None for r in items) else None for key in FIELDS[6:]}
    daily=[{'date':day,**totals([r for r in dated if r['date']==day])} for day in sorted({r['date'] for r in dated})]
    tracking_rows=[r for r in details if r['view']=='tracking_id']
    if not tracking_rows:tracking_rows=[r for r in rows if r['view']=='tracking_id']
    tracking=[{'tracking_id':tag,**totals([r for r in tracking_rows if r['tracking_id']==tag])} for tag in sorted({r['tracking_id'] for r in tracking_rows})]
    return {'totals':totals(rows),'rows':rows,'daily':daily,'tracking':tracking,
            'daily_limitation':'Seules les dates présentes dans les lignes des rapports de référence alimentent l’évolution. Les jours absents ne valent pas zéro. Les dates confirmées manuellement sont exclues.',
            'tracking_limitation':'Vue Tracking IDs séparée, jamais ajoutée aux totaux. Sa couverture peut différer de celle du rapport de référence.',
            'reports':[{**{k:r[k] for k in ('id','kind','start','end','scope','observed_at')},'view':r.get('view','legacy'),'contribution':r.get('contribution','totals')} for r in reports],
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


def ingest_portal_batch(db, identity, payload, day, expected_tag, observed):
    """Fail closed, atomic batch through the existing versioned importer."""
    if payload.get('complete') is not True or payload.get('day') != day:
        raise ValueError('Collecte Amazon incomplète ou période différente. Aucun import.')
    files=payload.get('files')
    if not isinstance(files,list) or len(files)!=3 or {f.get('view') for f in files}!={'category','linked_product','tracking_id'}:
        raise ValueError('Les trois vues Amazon attendues ne sont pas disponibles.')
    prepared=[]
    for file in files:
        text=file.get('csv')
        if file.get('archive'):
            members=inspect_archive(file)['files']
            if len(members)!=1:raise ValueError('Un seul CSV attendu par export Amazon.')
            text=members[0]['csv']
        headers,_=inspect_csv({'csv':text})
        mapping={'clicks':'clics','ordered_items':'articles commandés','shipped_items':'articles expédiés','commission_cents':'revenus totaux'}
        if file['view']=='tracking_id':mapping['tracking_id']='Numéro de suivi'
        else:
            mapping['date']='Date'
            mapping['title']='catégorie' if file['view']=='category' else 'titre du produit'
            if file['view']=='linked_product':mapping['asin']='ASIN'
        if not set(mapping.values())<=set(headers):raise ValueError('Colonnes Amazon non reconnues. Import manuel nécessaire.')
        data=dict(csv=text,mapping=mapping,kind='performance',view=file['view'],contribution='totals' if file['view']=='category' else 'detail',start=day,end=day,scope='all',single_day=file['view']=='tracking_id',date_format='mdy',decimal='dot',confirmed=True)
        value=normalize(data)
        if not value['rows']:raise ValueError('Rapport Amazon vide : couverture à vérifier manuellement.')
        if file['view']=='tracking_id' and expected_tag not in {r['tracking_id'] for r in value['rows']}:
            raise ValueError('Tracking ID attendu absent : compte ou périmètre Amazon à vérifier. Aucun import.')
        prepared.append(data)
    db.execute('SAVEPOINT amazon_portal_batch')
    try:
        results=[ingest(db,identity,data,observed) for data in prepared]
        db.execute('RELEASE amazon_portal_batch')
        return results
    except Exception:
        db.execute('ROLLBACK TO amazon_portal_batch');db.execute('RELEASE amazon_portal_batch');raise
