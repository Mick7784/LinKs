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
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

LIMIT = 8 * 1024 * 1024
API_LIMIT = 1024 * 1024
ARCHIVE_LIMIT = 16 * 1024 * 1024
EXPANDED_LIMIT = 64 * 1024 * 1024
ARCHIVE_BODY_LIMIT = ((ARCHIVE_LIMIT + 2) // 3) * 4 + 128 * 1024
FIELDS = ('date','tracking_id','asin','title','provider_status','transaction_id','orders','ordered_items','shipped_items','commission_cents','payment_cents','clicks')
METRICS = {'orders':('orders','ordered_items'), 'earnings':('shipped_items','commission_cents'), 'payments':('payment_cents',), 'performance':('clicks','ordered_items','shipped_items','commission_cents')}



VIEWS = {'legacy', 'category', 'linked_product', 'tracking_id', 'daily_trends'}

def inspect_archive(data):
    """Read bounded text members in memory. Never extract paths or import totals."""
    encoded=data.get('archive')
    if not isinstance(encoded,str) or len(encoded)>((ARCHIVE_LIMIT+2)//3)*4:
        raise ValueError('Archive ZIP limitée à 16 Mo.')
    try:
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>ARCHIVE_LIMIT: raise ValueError()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members=archive.infolist()
            if not 1<=len(members)<=64: raise ValueError()
            total=0;files=[];names=set()
            for entry in members:
                name=entry.filename
                if len(name)>1000 or name.startswith(('/', '\\')) or '\\' in name or ':' in name or '..' in name.split('/') or stat.S_ISLNK(entry.external_attr>>16): raise ValueError()
                if entry.is_dir(): continue
                if name in names or entry.flag_bits&1 or not name.lower().endswith(('.csv','.txt')): raise ValueError()
                names.add(name);total+=entry.file_size
                if total>EXPANDED_LIMIT or entry.file_size>LIMIT or entry.file_size>max(1024*1024,entry.compress_size*200) or entry.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED): raise ValueError()
                with archive.open(entry) as stream: payload=stream.read(LIMIT+1)
                if len(payload)!=entry.file_size: raise ValueError()
                encoding='utf-16' if payload.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'
                try:text=payload.decode(encoding)
                except UnicodeDecodeError:
                    encoding='cp1252'
                    text=payload.decode('cp1252')
                    if not any(len(next(csv.reader([line],delimiter=delimiter)))>=2 for line in text.splitlines()[:101] for delimiter in (',',';','\t')):raise ValueError()
                if any(ord(c)<32 and c not in '\r\n\t' for c in text): raise ValueError()
                files.append({'name':name,'csv':text,'encoding':encoding})
            if not files: raise ValueError()
            return {'files':files,'imported':False,'digest':hashlib.sha256(raw).hexdigest()}
    except (ValueError,binascii.Error,zipfile.BadZipFile,RuntimeError,NotImplementedError,OSError,UnicodeError):
        raise ValueError('ZIP invalide : CSV/TXT UTF-8, UTF-16 avec BOM ou Windows-1252, 64 entrées, 8 Mo par fichier et 64 Mo décompressés maximum, ratio borné, sans chiffrement ni chemins dangereux.') from None


def inspect_csv(data):
    text=data.get('csv')
    if not isinstance(text,str) or not text.strip() or len(text.encode('utf-8'))>LIMIT:
        raise ValueError('Rapport CSV UTF-8 requis, limité à 8 Mo.')
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


# Exact numeric-row fingerprints of annual exports confirmed by their owner.
# No merchant names, product IDs or monetary amounts are embedded here.
MISDATED_ANNUAL_EXPORTS = {
    'dc42ab95d73bd94b394ef3d484868871a95fe324cddf7ca10bbf37ba78e11a70',
    'e4a44e0e4cd453ef5e015b6ddc6aaf39988926efe9a8685e42117d2bd66a96ef',
    'cfd04b5f12a31bf41a68f800f9d955220f40ff4afbcf26470781c8a13ad22792',
}

def financial_rows_fingerprint(value):
    cells=[[r.get(k) for k in ('clicks','ordered_items','shipped_items','commission_cents')] for r in value['rows']]
    cells=[r for r in cells if any(r)]
    return hashlib.sha256(json.dumps(sorted(cells,key=lambda r:json.dumps(r)),separators=(',',':')).encode()).hexdigest()

def misdated_annual_export(value):
    return value.get('date_basis')!='confirmed_period' and financial_rows_fingerprint(value) in MISDATED_ANNUAL_EXPORTS

def resolved_reports(db,identity):
    latest={}
    for row in db.execute('SELECT * FROM aff_snapshots WHERE account_id=? ORDER BY id',(identity,)):
        value=json.loads(row['summary']).get('amazon')
        if value:
            latest={key:report for key,report in latest.items() if report['id'] not in value.get('supersedes',[])}
            latest[(value['kind'],value['start'],value['end'],value['scope'],value.get('view','legacy'),value.get('contribution','totals'),tuple(sorted(reference_metrics(value))))]={'id':row['id'],'observed_at':row['observed_at'],**value}
    return list(latest.values())

def active_reports(db,identity):
    # Apply supersession before exclusion: never resurrect an older bad import.
    # Snapshots remain byte-for-byte intact, including during backup/restore.
    return [r for r in resolved_reports(db,identity) if not misdated_annual_export(r)]


def validate_saved(value):
    if not isinstance(value,dict) or set(value)-{'view','date_basis','contribution','archive_digest','supersedes','reference_metrics','filename'}!={'version','kind','start','end','scope','currency','rows','digest'} or value['version']!=1 or value['currency']!='EUR':raise ValueError('Rapport Amazon sauvegardé invalide.')
    if value.get('contribution','totals') not in {'totals','detail'}: raise ValueError('Usage sauvegardé invalide.')
    if 'date_basis' in value and value['date_basis'] not in {'confirmed_single_day','confirmed_period'}: raise ValueError('Origine de date invalide.')
    if value.get('date_basis')=='confirmed_single_day' and value['start']!=value['end']: raise ValueError('Origine de date invalide.')
    if 'archive_digest' in value and not re.fullmatch(r'[a-f0-9]{64}',value['archive_digest']): raise ValueError('Empreinte archive invalide.')
    if 'supersedes' in value and (not isinstance(value['supersedes'],list) or any(type(v) is not int or v<=0 for v in value['supersedes'])): raise ValueError('Historique invalide.')
    if 'filename' in value and (not isinstance(value['filename'],str) or len(value['filename'])>1000): raise ValueError('Nom invalide.')
    if 'reference_metrics' in value and (not isinstance(value['reference_metrics'],list) or not set(value['reference_metrics'])<=set(METRICS[value['kind']])): raise ValueError('Indicateurs de référence invalides.')
    if value.get('view','legacy') not in VIEWS: raise ValueError('Vue Amazon sauvegardée invalide.')
    if value['kind'] not in METRICS or not isinstance(value['rows'],list) or len(value['rows'])>10000:raise ValueError('Rapport Amazon sauvegardé invalide.')
    if date.fromisoformat(value['start'])>date.fromisoformat(value['end']) or not re.fullmatch(r'(all|[A-Za-z0-9_-]{1,100})',value['scope']):raise ValueError('Périmètre Amazon invalide.')
    for row in value['rows']:
        if not isinstance(row,dict) or set(row) not in (set(FIELDS),set(FIELDS)-{'clicks'}):raise ValueError('Ligne Amazon invalide.')
        if value.get('date_basis')=='confirmed_period':
            if row['date'] is not None: raise ValueError('Date quotidienne inventée.')
        elif not value['start']<=date.fromisoformat(row['date']).isoformat()<=value['end']:raise ValueError('Date Amazon invalide.')
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
    supersedes=[]
    for previous in active_reports(db,identity):
        same=all(previous[k]==value[k] for k in ('kind','start','end','scope'))
        same_view=previous.get('view','legacy')==value.get('view','legacy')
        same_usage=previous.get('contribution','totals')==value.get('contribution','totals')
        if same and same_view and same_usage and (previous.get('digest')==digest or all(previous.get(k)==v for k,v in value.items())):return {'ok':True,'duplicate':True,'rows':len(value['rows'])}
        overlap=previous['start']<=value['end'] and value['start']<=previous['end']
        shared=previous['scope']==value['scope'] or 'all' in (previous['scope'],value['scope'])
        financial=previous.get('contribution','totals')=='totals' and value.get('contribution','totals')=='totals'
        common=available_metrics(previous) & available_metrics(value)
        if overlap and shared and common and (financial or (same_usage and same_view)):
            if not (same and same_view and same_usage):
                raise ValueError('Indicateurs et périodes chevauchants : utilisez une vue complémentaire pour éviter le double comptage. Une correction doit conserver la même vue et le même périmètre.')
            if not (reference_metrics(previous) if financial else available_metrics(previous))<=available_metrics(value):
                raise ValueError('La correction CSV doit conserver les indicateurs existants. Utilisez le ZIP automatique pour une mise à jour partielle.')
            supersedes.append(previous['id'])
    if supersedes:value['supersedes']=supersedes
    value['digest']=hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    db.execute('INSERT INTO aff_snapshots(account_id,observed_at,summary,row_count,pages,source) VALUES(?,?,?,?,1,?)',
               (identity,observed,json.dumps({'amazon':value}),len(value['rows']),'amazon-csv'))
    db.execute('UPDATE aff_accounts SET last_success=?,last_error=NULL WHERE id=?',(observed,identity))
    return {'ok':True,'duplicate':False,'rows':len(value['rows'])}


def field_key(value):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD',value.lower()).encode('ascii','ignore').decode())


AUTO_COLUMNS = {
    'date': ('date','day','jour','date de commande','date shipped'),
    'tracking_id': ('tracking id','tracking-id','numero de suivi','tag','identifiant de suivi'),
    'asin': ('asin',), 'title': ('title','product title','titre du produit','titre de produit','produit','category','categorie'),
    'clicks': ('clicks','clics'), 'orders': ('orders','commandes'),
    'ordered_items': ('ordered items','items ordered','articles commandes','commandes articles'),
    'shipped_items': ('shipped items','items shipped','articles expedies','expedies'),
    'commission_cents': ('commission','commissions','earnings','total earnings','revenus totaux','remunerations','advertising fees'),
    'payment_cents': ('payment','payments','paiement','paiements'),
}
AUTO_ALIASES = {field_key(alias):key for key,aliases in AUTO_COLUMNS.items() for alias in aliases}


def auto_day(value):
    value=value.strip()
    for pattern,format in [(r'\d{4}-\d{2}-\d{2}','%Y-%m-%d'),(r'\d{2}-\d{2}-\d{4}','%m-%d-%Y'),(r'\d{2}/\d{2}/\d{4}','%d/%m/%Y')]:
        if re.fullmatch(pattern,value): return datetime.strptime(value,format).date().isoformat()
    raise ValueError('Date Amazon non reconnue : ISO, MM-JJ-AAAA ou JJ/MM/AAAA attendus.')


class ComplementaryReport(ValueError):
    """Recognized non-financial evidence, not a parser failure."""


def column_key(header):
    return AUTO_ALIASES.get(field_key(re.sub(r'\s*[\[(]?(?:EUR|€)[\])]?\s*$', '',header,flags=re.I)))


def numeric_cell(raw):
    raw=re.sub(r'EUR|€|\s', '',raw,flags=re.I)
    if ',' in raw and '.' in raw:
        return raw.replace('.','').replace(',','.') if raw.rfind(',')>raw.rfind('.') else raw.replace(',','')
    return raw.replace(',','.')


def resolve_columns(headers,keys,rows):
    """Position remains the identity; never choose a conflicting duplicate by order."""
    keys=list(keys);notes=[]
    if any(field_key(h) in {'title','producttitle','titreduproduit','titredeproduit','produit'} for h in headers):
        keys=[None if field_key(h) in {'category','categorie'} else k for h,k in zip(headers,keys)]
    for key in dict.fromkeys(k for k in keys if k):
        positions=[i for i,k in enumerate(keys) if k==key]
        if len(positions)<2:continue
        populated=[i for i in positions if any(r[i].strip() not in {'','-'} for r in rows)]
        candidates=populated or positions
        def canonical(raw):
            raw=raw.strip()
            if raw in {'','-'}:return None
            if key=='date':return auto_day(raw)
            if key in FIELDS[6:]:
                value=Decimal(numeric_cell(raw))
                scaled=value*(100 if key.endswith('_cents') else 1)
                if not value.is_finite() or abs(scaled)>10**14 or abs(scaled-scaled.to_integral_value())>Decimal('0.00000001'):raise ValueError()
                return value
            if key=='asin' and not re.fullmatch(r'[A-Z0-9]{10}',raw):raise ValueError()
            return raw
        try:
            columns=[[canonical(r[i]) for r in rows] for i in candidates]
            equivalent=all(c==columns[0] for c in columns)
        except (ValueError,InvalidOperation):equivalent=False
        if not equivalent:
            locations=', '.join(f'{i+1} « {headers[i]} »' for i in positions)
            raise ValueError(f'Colonnes ambiguës pour {key} : {locations}. Contenus ou formats incompatibles ; aucune colonne sélectionnée.')
        selected=candidates[0]
        for i in positions:
            if i!=selected:keys[i]=None
        notes.append(f'Colonnes {", ".join(str(i+1) for i in positions)} ({key}) : colonne {selected+1} retenue ; doublons équivalents ou colonnes entièrement vides.')
    return keys,notes


def auto_report(file,override,diagnostic=None):
    """Detect known export columns; missing coverage is returned, never guessed."""
    lines=file['csv'].lstrip('\ufeff').splitlines(); candidates=[];rankings=[]
    for offset,line in enumerate(lines[:101]):
        for delimiter in (';',',','\t'):
            headers=next(csv.reader([line],delimiter=delimiter))
            keys=[column_key(h) for h in headers]
            names={field_key(h) for h in headers}
            if 'asin' in names and names & {'rank','rang','classement','salesrank','bestsellerrank'}:
                rankings.append((offset,delimiter,headers))
            score=sum(k in FIELDS[6:] for k in keys)
            if score: candidates.append((score,offset,delimiter,headers,keys))
    if not candidates:
        if rankings:
            offset,delimiter,headers=rankings[0]
            if len(headers)>100 or any(len(h)>500 for h in headers):raise ValueError('En-tête Top-Sellers trop long.')
            rows=list(csv.reader(io.StringIO('\n'.join(lines[offset+1:])),delimiter=delimiter,strict=True))
            rows=[r for r in rows if any(c.strip() for c in r) and r!=headers]
            if not rows or len(rows)>10000 or any(len(r)!=len(headers) for r in rows):raise ValueError('Classement Top-Sellers : lignes CSV invalides ou vides.')
            asins=[i for i,h in enumerate(headers) if field_key(h)=='asin']
            ranks=[i for i,h in enumerate(headers) if field_key(h) in {'rank','rang','classement','salesrank','bestsellerrank'}]
            if len(asins)!=1 or len(ranks)!=1 or any(not re.fullmatch(r'[A-Z0-9]{10}',r[asins[0]].strip()) or not re.fullmatch(r'[1-9]\d*',r[ranks[0]].strip()) for r in rows):
                raise ValueError('Classement Top-Sellers : colonnes ou valeurs de rang/ASIN non fiables.')
            if diagnostic is not None:diagnostic.update(header_row=offset+1,delimiter=delimiter,headers=headers,row_count=len(rows))
            raise ComplementaryReport('Classement Top-Sellers reconnu : informations complémentaires sans indicateur financier reconnu ; conservé hors statistiques.')
        raise ValueError('Aucun en-tête Amazon reconnu.')
    _,offset,delimiter,headers,keys=max(candidates,key=lambda c:(c[0],-c[1]))
    if len(headers)>100 or any(len(h)>500 for h in headers):raise ValueError('En-tête trop long ou plus de 100 colonnes : format non pris en charge.')
    if diagnostic is not None:diagnostic.update(header_row=offset+1,delimiter=delimiter,headers=headers)
    rows=list(csv.reader(io.StringIO('\n'.join(lines[offset+1:])),delimiter=delimiter,strict=True))
    rows=[r for r in rows if any(c.strip() for c in r) and r!=headers]
    if len(rows)>10000 or any(len(r)!=len(headers) for r in rows): raise ValueError('Lignes CSV invalides ou plus de 10 000 lignes.')
    keys,warnings=resolve_columns(headers,keys,rows)
    recognized=[k for k in keys if k]
    if diagnostic is not None:diagnostic.update(row_count=len(rows),columns=[{'position':i+1,'header':h,'role':keys[i]} for i,h in enumerate(headers)],corrections=warnings[:])
    clean=[]
    for row in rows:
        if any(field_key(row[i]) in {'total','totals','totalgeneral','grandtotal','subtotal','soustotal'} for i,k in enumerate(keys) if k in {'title','date','tracking_id'}):
            warnings.append('Ligne de total exclue.');continue
        clean.append({key:row[i].strip() for i,key in enumerate(keys) if key})
    if not clean: raise ValueError('Rapport vide : couverture impossible à établir.')
    preamble='\n'.join(lines[:offset])
    # Filename date ranges and labelled preambles are export evidence. Never use
    # file timestamps, upload dates, or the date filter currently open in the UI.
    token=r'(?:\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})'
    ranges=[]
    for line in [file['name'], *preamble.splitlines()]:
        if line!=file['name'] and not re.search(r'period|période|date|from|du ',line,re.I): continue
        dates=re.findall(token,line)
        if len(dates)==2:ranges.append(tuple(auto_day(d) for d in dates))
    if len(set(ranges))>1: raise ValueError('Périodes contradictoires dans le rapport.')
    # Native category/product exports use Date as a report marker even for YTD
    # aggregates. It does not establish the date of the underlying commissions.
    header_keys={field_key(h) for h in headers}
    aggregate_export=('asin' in recognized or bool(header_keys & {'category','categorie'})) and bool(header_keys & {'tauxdeconversiondirect','directconversionrate'}) and bool(header_keys & {'articlesretournes','returneditems','itemsreturned'})
    dated='date' in recognized and not aggregate_export
    if aggregate_export:
        for row in clean:row.pop('date',None)
        warnings.append('Export agrégé : la colonne Date est un repère du rapport, pas la date de chaque commission. La période complète doit être confirmée ; aucune ventilation quotidienne ne sera créée.')
    if dated:
        for row in clean: row['date']=auto_day(row['date'])
    period=ranges[0] if ranges else ((min(r['date'] for r in clean),max(r['date'] for r in clean)) if dated else None)
    if override.get('start') or override.get('end'):
        provided=(auto_day(override.get('start','')),auto_day(override.get('end','')))
        if ranges and provided!=ranges[0]: raise ValueError('La période saisie contredit le rapport.')
        period=provided
    scopes=re.findall(r'(?:tracking[ -]?ids?|numéro de suivi|scope|périmètre)\s*[:=;\t]\s*([^\r\n;\t]+)',preamble,re.I)
    scopes=[s.strip() for s in scopes]
    scopes=['all' if field_key(s) in {'all','alltrackingids','tous','touslestrackingids','touslesidentifiantsdesuivi'} else s for s in scopes]
    if len(set(scopes))>1: raise ValueError('Périmètres contradictoires dans le rapport.')
    scope=scopes[0] if scopes else override.get('scope')
    if scopes and override.get('scope') and override['scope']!=scope: raise ValueError('Le périmètre saisi contredit le rapport.')
    currencies=set(re.findall(r'\b(?:EUR|USD|GBP|CAD|JPY)\b',preamble+' '+','.join(headers)+' '+' '.join(v for r in clean for k,v in r.items() if k.endswith('_cents')),re.I))
    if any('€' in v for r in clean for k,v in r.items() if k.endswith('_cents')) or '€' in ','.join(headers): currencies.add('EUR')
    currencies={c.upper() for c in currencies}
    if currencies-{'EUR'}: raise ValueError('Devise non EUR ou devises mélangées : aucun import.')
    currency='EUR' if currencies else str(override.get('currency','')).strip().upper()
    needed=[]
    if period is None:needed.extend(['start','end'])
    if not scope:needed.append('scope')
    if not currency:needed.append('currency')
    if needed:return None,{'name':file['name'],'fields':needed},warnings
    if currency!='EUR':raise ValueError('Seuls les montants EUR sont pris en charge.')
    view=('linked_product' if 'asin' in recognized or any(field_key(h) in {'producttitle','titreduproduit','titredeproduit','produit'} for h in headers) else 'category' if any(field_key(h) in {'category','categorie'} for h in headers) else 'tracking_id' if 'tracking_id' in recognized else 'daily_trends' if dated else 'legacy')
    metrics=set(recognized)&set(FIELDS[6:])
    kind=next((k for k in ('payments','orders','earnings','performance') if metrics<=set(METRICS[k])),None)
    if not kind: raise ValueError('Mélange de métriques incompatible avec les rapports connus.')
    for row in clean:
        for key in metrics:
            row[key]=numeric_cell(row[key])
        if not dated:row['date']=period[0]
    output=io.StringIO(); writer=csv.DictWriter(output,fieldnames=list(clean[0]));writer.writeheader();writer.writerows(clean)
    value=normalize(dict(csv=output.getvalue(),mapping={k:k for k in clean[0]},kind=kind,view=view,start=period[0],end=period[1],scope=scope,decimal='dot'))
    if not dated:
        value['date_basis']='confirmed_period'
        for row in value['rows']:row['date']=None
        warnings.append('Total de période sans ventilation quotidienne.')
    value['view']=view
    value['filename']=file['name']
    return value,None,list(dict.fromkeys(warnings))


def reference_metrics(value):
    if value.get('contribution','totals')!='totals':return set()
    return set(value.get('reference_metrics',METRICS[value['kind']])) & available_metrics(value)


def available_metrics(value):
    return {key for key in METRICS[value['kind']] if any(r.get(key) is not None for r in value['rows'])}


def metric_totals(rows):
    return {key:sum(r.get(key) or 0 for r in rows) if any(r.get(key) is not None for r in rows) else None for key in FIELDS[6:]}


def ingest_archive(db,identity,data,observed):
    archive=inspect_archive(data)
    # Historical fingerprints are intentional: an old archive must not undo a correction.
    if any(json.loads(r['summary']).get('amazon',{}).get('archive_digest')==archive['digest'] for r in db.execute('SELECT summary FROM aff_snapshots WHERE account_id=?',(identity,))):
        return {'ok':True,'duplicate':True,'imported':False}
    prepared=[];needs=[];warnings=[]
    overrides=data.get('coverage',{})
    if not isinstance(overrides,dict):raise ValueError('Précisions de couverture invalides.')
    for file in archive['files']:
        try:
            override=overrides.get(file['name'],{})
            if not isinstance(override,dict):raise ValueError('Précisions invalides.')
            value,missing,notes=auto_report(file,override)
        except (ValueError,csv.Error) as exc: raise ValueError(file['name']+' : '+str(exc)) from None
        warnings.extend(file['name']+' : '+note for note in notes)
        if missing:needs.append(missing)
        else:prepared.append(value)
    if needs:return {'ok':False,'imported':False,'needs':needs,'warnings':warnings}
    groups={}
    for value in prepared:groups.setdefault((value['start'],value['end'],value['scope']),[]).append(value)
    for group in groups.values():
        identities=[(v['kind'],v.get('view','legacy')) for v in group]
        if len(set(identities))!=len(identities):raise ValueError('Plusieurs fichiers de la même vue et du même périmètre : archive ambiguë.')
        for value in group:value['reference_metrics']=[]
        for metric in FIELDS[6:]:
            choices=[v for v in group if any(r[metric] is not None for r in v['rows'])]
            if not choices:continue
            rank={'category':0,'daily_trends':1,'tracking_id':2,'linked_product':3,'legacy':4}
            choices.sort(key=lambda v:(rank[v.get('view','legacy')],v['filename']))
            reference=choices[0];amount=metric_totals(reference['rows'])[metric]
            daily=[v for v in choices if not v.get('date_basis') and metric_totals(v['rows'])[metric]==amount]
            if daily:reference=daily[0]
            reference['reference_metrics'].append(metric)
            if any(metric_totals(v['rows'])[metric]!=amount for v in choices):warnings.append('Vues divergentes pour '+metric+' : seule la référence '+reference['filename']+' est comptabilisée.')
        for value in group:value['contribution']='totals' if value['reference_metrics'] else 'detail'
    # Validate every overlap before the first write, including overlaps within the ZIP.
    previous=active_reports(db,identity);supersedes=[]
    for i,value in enumerate(prepared):
        for other in prepared[:i]:
            if value['start']<=other['end'] and other['start']<=value['end'] and (value['scope']==other['scope'] or 'all' in (value['scope'],other['scope'])) and reference_metrics(value)&reference_metrics(other):
                raise ValueError('Chevauchement incompatible dans le ZIP : '+value['filename']+' / '+other['filename'])
    for old in previous:
        conflicts=[v for v in prepared if old['start']<=v['end'] and v['start']<=old['end'] and (old['scope']==v['scope'] or 'all' in (old['scope'],v['scope'])) and reference_metrics(old)&reference_metrics(v)]
        if not conflicts:continue
        exact=all(all(old[k]==v[k] for k in ('start','end','scope')) for v in conflicts)
        covered=set().union(*(reference_metrics(v) for v in conflicts))
        old_metrics={m for m in reference_metrics(old) if any(r.get(m) is not None for r in old['rows'])}
        if not exact or not old_metrics<=covered:
            raise ValueError(f"Chevauchement incompatible avec le rapport #{old['id']} ({old['start']} → {old['end']}, {old['scope']}). Conservez exactement la période, le périmètre et les indicateurs à remplacer.")
        supersedes.append(old['id'])
    replaced_groups={(r['start'],r['end'],r['scope']) for r in previous if r['id'] in supersedes}
    supersedes.extend(r['id'] for r in previous if r.get('contribution')=='detail' and (r['start'],r['end'],r['scope']) in replaced_groups)
    db.execute('SAVEPOINT amazon_zip')
    try:
        for i,value in enumerate(prepared):
            value['archive_digest']=archive['digest']
            if i==0:value['supersedes']=supersedes
            value['digest']=hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            validate_saved(value)
            db.execute('INSERT INTO aff_snapshots(account_id,observed_at,summary,row_count,pages,source) VALUES(?,?,?,?,1,?)',(identity,observed,json.dumps({'amazon':value}),len(value['rows']),'amazon-zip'))
        db.execute('UPDATE aff_accounts SET last_success=?,last_error=NULL WHERE id=?',(observed,identity))
        db.execute('RELEASE amazon_zip')
    except Exception:
        db.execute('ROLLBACK TO amazon_zip');db.execute('RELEASE amazon_zip');raise
    counted=[{k:r.get(k) if k in reference_metrics(v) else None for k in FIELDS[6:]} for v in prepared for r in v['rows']]
    return {'ok':True,'imported':True,'duplicate':False,'files':[{'name':v['filename'],'view':v.get('view','legacy'),'start':v['start'],'end':v['end'],'scope':v['scope'],'reference_metrics':v['reference_metrics']} for v in prepared], 'totals':metric_totals(counted),'warnings':warnings,'replaced':len(supersedes)}


def report(db,identity,start='',end=''):
    reports=active_reports(db,identity);rows=[];details=[];dated=[];undated=[];excluded=[]
    for source in reports:
        period=source.get('date_basis')=='confirmed_period'
        contained=(not start or source['start']>=start) and (not end or source['end']<=end)
        if period and not contained and (not start or source['end']>=start) and (not end or source['start']<=end):excluded.append(source['id'])
        selected=[{**r,'coverage':(source['start'],source['end']) if period else r['date'],'clicks':r.get('clicks'),'kind':source['kind'],'view':source.get('view','legacy')} for r in source['rows'] if (contained if period else (not start or r['date']>=start) and (not end or r['date']<=end))]
        if source.get('contribution','totals')=='totals':
            selected=[{**r,**{k:None for k in FIELDS[6:] if k not in reference_metrics(source)}} for r in selected]
            rows.extend(selected)
            if not source.get('date_basis'):dated.extend(selected)
            else:undated.extend(selected)
        else:details.extend(selected)
    def totals(items):
        return {key:sum(r.get(key) or 0 for r in items) if any(r.get(key) is not None for r in items) else None for key in FIELDS[6:]}
    daily=[{'date':day,**totals([r for r in dated if r['date']==day])} for day in sorted({r['date'] for r in dated})]
    # Prefer details only on their actual day/tag/metric coverage.
    tracking_rows=[r for r in details if r['view']=='tracking_id']
    coverage={}
    def interval(row):return row['coverage'] if isinstance(row['coverage'],tuple) else (row['date'],row['date'])
    for r in tracking_rows:
        for key in FIELDS[6:]:
            if r.get(key) is not None:coverage.setdefault((r['tracking_id'],key),[]).append(interval(r))
    for key,spans in coverage.items():
        merged=[]
        for start_day,end_day in sorted(spans):
            if merged and start_day<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end_day,merged[-1][1]))
            else:merged.append((start_day,end_day))
        coverage[key]=merged
    tracking_partial=False
    for row in rows:
        if row['view']!='tracking_id':continue
        value=dict(row);first,last=interval(row)
        for key in FIELDS[6:]:
            spans=coverage.get((row['tracking_id'],key),[])
            if row.get(key) is not None and any(a<=last and first<=b for a,b in spans):
                value[key]=None
                # An undated aggregate cannot be subtracted or prorated to fill a gap.
                if row['date'] is None and not any(a<=first and b>=last for a,b in spans):tracking_partial=True
        tracking_rows.append(value)
    tracking=[{'tracking_id':tag,**totals([r for r in tracking_rows if r['tracking_id']==tag])} for tag in sorted({r['tracking_id'] for r in tracking_rows})]
    return {'totals':totals(rows),'rows':rows,'daily':daily,'tracking':tracking,'tracking_partial':tracking_partial,'undated_totals':totals(undated),'excluded_period_reports':excluded,
            'quarantined_reports':[{'id':r['id'],'start':r['start'],'end':r['end'],'reason':'Cumul annuel identifié : dates quotidiennes invalides. Rapport conservé dans l’historique et exclu des statistiques.'} for r in resolved_reports(db,identity) if misdated_annual_export(r)],
            'daily_limitation':'Seules les dates présentes dans les lignes des rapports de référence alimentent l’évolution. Les jours absents ne valent pas zéro. Les dates confirmées manuellement sont exclues.',
            'tracking_limitation':'Vue Tracking IDs séparée, jamais ajoutée aux totaux. '+('Couverture partielle : un total non daté chevauchant ne peut pas être réparti.' if tracking_partial else 'Sa couverture peut différer de celle du rapport de référence.'),
            'reports':[{**{k:r[k] for k in ('id','kind','start','end','scope','observed_at')},'filename':r.get('filename'),'date_basis':r.get('date_basis'),'view':r.get('view','legacy'),'contribution':r.get('contribution','totals')} for r in reports],
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
            raw=response.read(API_LIMIT+1)
        if len(raw)>API_LIMIT:raise ValueError()
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
        with build_opener(NoRedirect).open(Request(url),timeout=25) as response:raw=response.read(API_LIMIT+1)
        if len(raw)>API_LIMIT:raise ValueError()
        text=raw.decode('utf-8-sig')
        inspect_csv({'csv':text})
        return {'csv':text}
    except Exception:raise ValueError('Rapport non exploitable en CSV UTF-8 (1 Mo maximum). Utilisez un export CSV du portail.') from None


def ingest_portal_batch(db, identity, payload, day, expected_tag, observed):
    """Fail closed, atomic batch through the existing versioned importer."""
    if payload.get('complete') is not True or payload.get('day') != day:
        raise ValueError('Collecte Amazon incomplète ou période différente. Aucun import.')
    if payload.get('scope')!={'value':'all','verified':True,'method':'portal_tracking_filter'}:
        raise ValueError('Périmètre tous les Tracking IDs non vérifié. Dernier relevé conservé.')
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
    totals=[metric_totals(normalize(data)['rows']) for data in prepared]
    if any(len({t[key] for t in totals if t[key] is not None})>1 for key in FIELDS[6:]):
        raise ValueError('Les trois vues Amazon divergent. Dernier relevé conservé.')
    db.execute('SAVEPOINT amazon_portal_batch')
    try:
        results=[ingest(db,identity,data,observed) for data in prepared]
        db.execute('RELEASE amazon_portal_batch')
        return results
    except Exception:
        db.execute('ROLLBACK TO amazon_portal_batch');db.execute('RELEASE amazon_portal_batch');raise
