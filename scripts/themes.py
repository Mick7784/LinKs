"""Versioned appearance data. Only typed allowlisted tokens reach public CSS."""
import base64, binascii, json, re, uuid
import images
import storage
from pathlib import Path

FORMAT='links-theme'
VERSION=1
MAX_BYTES=12*1024*1024
ORIGINAL='links-original'
ROOT=Path(__file__).resolve().parent.parent
STATIC=ROOT/'site' if (ROOT/'site').exists() else Path('/usr/share/nginx/html')
SCHEMA=json.loads((STATIC/'theme-tokens.json').read_text(encoding='utf-8'))['tokens']
LIBRARY=json.loads((STATIC/'asset-library.json').read_text(encoding='utf-8'))
BACKGROUNDS={x['id']:x['url'] for x in LIBRARY['backgrounds']}
UPLOAD=re.compile(r'/uploads/[a-f0-9-]{36}\.(png|jpg|webp|gif)')
KEYS={'appearance.themes','appearance.active'}

def initialize(db):
    db.execute("INSERT OR IGNORE INTO settings VALUES('appearance.themes','[]')")
    db.execute("INSERT OR IGNORE INTO settings VALUES('appearance.active',?)",(ORIGINAL,))

def validate_tokens(values):
    if not isinstance(values,dict) or len(values)>len(SCHEMA):raise ValueError('Variables de thème invalides')
    result={}
    for key,value in values.items():
        if key not in SCHEMA:raise ValueError('Variable non autorisée : '+str(key))
        spec=SCHEMA[key];kind=spec['type']
        if kind=='color':
            valid=isinstance(value,str) and bool(re.fullmatch(r'#[a-fA-F0-9]{6}(?:[a-fA-F0-9]{2})?',value))
        elif kind in {'length','number'}:
            valid=type(value) in {int,float} and spec['min']<=value<=spec['max']
        elif kind=='enum':valid=isinstance(value,str) and value in spec['options']
        elif kind=='image':valid=isinstance(value,str) and (value=='none' or value.startswith('system:') and value[7:] in BACKGROUNDS or bool(UPLOAD.fullmatch(value)))
        else:valid=False
        if not valid:raise ValueError('Valeur invalide : '+key)
        result[key]=value
    return result

def record(data):
    if not isinstance(data,dict):raise ValueError('Thème invalide')
    name=data.get('name');author=data.get('author','')
    if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('Nom de thème requis (80 caractères maximum)')
    if not isinstance(author,str) or len(author)>100:raise ValueError('Auteur invalide')
    if set(data)-{'id','name','author','tokens'}:raise ValueError('Propriété de thème non autorisée')
    return {'id':data.get('id') or str(uuid.uuid4()),'name':name.strip(),'author':author,'tokens':validate_tokens(data.get('tokens',{}))}

def state(db):
    rows=json.loads(db.execute("SELECT value FROM settings WHERE key='appearance.themes'").fetchone()[0])
    active=db.execute("SELECT value FROM settings WHERE key='appearance.active'").fetchone()[0]
    return {'active':active,'items':[{'id':ORIGINAL,'name':'LinKs Original','author':'LinKs','tokens':{},'system':True},*rows]}

def public(db):
    data=state(db)
    return next(x for x in data['items'] if x['id']==data['active'])

def references(rows):
    return {v for row in rows for k,v in row.get('tokens',{}).items() if SCHEMA[k]['type']=='image' and v.startswith('/uploads/')}

def save(db,data,uploads):
    db.execute('BEGIN IMMEDIATE')
    current=state(db);rows=current['items'][1:];action=data.get('action','save');target=data.get('id')
    existing=next((x for x in rows if x['id']==target),None)
    if action in {'activate','delete','duplicate'}:
        if target!=ORIGINAL and existing is None:raise ValueError('Thème introuvable')
        if action=='activate':
            db.execute("UPDATE settings SET value=? WHERE key='appearance.active'",(target,));return state(db)
        if action=='delete':
            if target==ORIGINAL:raise ValueError('LinKs Original est permanent')
            rows=[x for x in rows if x['id']!=target]
            if current['active']==target:db.execute("UPDATE settings SET value=? WHERE key='appearance.active'",(ORIGINAL,))
        else:
            if len(rows)>=3:raise ValueError('Maximum 3 thèmes personnalisés')
            source=existing or current['items'][0]
            rows.append(record({'name':source['name']+' (copie)','author':source['author'],'tokens':source['tokens']}))
    elif action=='save':
        incoming=record(data.get('theme'))
        if incoming['id']==ORIGINAL:raise ValueError('LinKs Original ne peut pas être écrasé')
        if target and incoming['id']!=target:raise ValueError('Identifiant incompatible')
        for ref in references([incoming]):
            storage.require_file(uploads,ref,db)
        found=next((x for x in rows if x['id']==incoming['id']),None)
        if found:rows[rows.index(found)]=incoming
        else:
            if len(rows)>=3:raise ValueError('Maximum 3 thèmes personnalisés')
            if not re.fullmatch(r'[a-f0-9-]{36}',incoming['id']):raise ValueError('Identifiant de thème invalide')
            rows.append(incoming)
        if data.get('publish') is True:db.execute("UPDATE settings SET value=? WHERE key='appearance.active'",(incoming['id'],))
    else:raise ValueError('Action inconnue')
    db.execute("UPDATE settings SET value=? WHERE key='appearance.themes'",(json.dumps(rows),))
    return state(db)

def css_export(theme):
    lines=['/* LinKs — variables autorisées uniquement ; format 1 */',':root {'];group=None
    for key,spec in SCHEMA.items():
        if group!=spec['group']:group=spec['group'];lines.append('  /* '+group+' */')
        value=theme['tokens'].get(key,spec['default'])
        if spec['type']=='length':value=str(value)+'px'
        lines.append('  '+key+': '+str(value)+'; /* '+spec['label']+' */')
    return '\n'.join([*lines,'}'])+'\n'

def css_import(value):
    if not isinstance(value,str) or len(value)>65536:raise ValueError('CSS trop volumineux')
    clean=re.sub(r'/\*.*?\*/','',value,flags=re.S);values={};errors=[];ignored=bool(re.search(r'(?<!-)\b(?:display|position|width|height|transform)\s*:',clean))
    for key,raw in re.findall(r'(--links-[\w-]+)\s*:\s*([^;{}]+)',clean):
        if key not in SCHEMA:errors.append('Variable inconnue : '+key);continue
        spec=SCHEMA[key];raw=raw.strip()
        try:
            if spec['type'] in {'length','number'}:
                pattern=r'-?\d+(?:\.\d+)?'+(r'px' if spec['type']=='length' else '')
                if not re.fullmatch(pattern,raw):raise ValueError('Unité invalide : '+key)
                raw=float(raw.removesuffix('px'))
            values.update(validate_tokens({key:raw}))
        except ValueError as exc:errors.append(str(exc))
    if errors:raise ValueError('\n'.join(errors))
    if not values:raise ValueError('Aucune variable LinKs reconnue')
    return {'tokens':values,'ignored_rules':ignored}

def image_valid(raw,ext):
    try:images.validate(raw,ext);return True
    except ValueError:return False

def export(theme,uploads):
    assets={}
    for ref in references([theme]):
        raw=(uploads/ref[9:]).read_bytes()
        if len(raw)>4*1024*1024:raise ValueError('Image trop volumineuse')
        assets[ref]=base64.b64encode(raw).decode('ascii')
    return {'format':FORMAT,'version':VERSION,'compatibility':{'engine':1},'theme':{k:v for k,v in theme.items() if k in {'name','author','tokens'}},'assets':assets}

def import_package(db,package,uploads):
    if not isinstance(package,dict) or package.get('format')!=FORMAT or type(package.get('version')) is not int or package['version']!=VERSION:raise ValueError('Format de thème incompatible')
    compatibility=package.get('compatibility')
    if not isinstance(compatibility,dict) or set(compatibility)!={'engine'} or type(compatibility.get('engine')) is not int or compatibility['engine']!=1:raise ValueError('Moteur de thème incompatible')
    if set(package)-{'format','version','compatibility','theme','assets'}:raise ValueError('Code ou fichier arbitraire interdit')
    if len(json.dumps(package).encode())>MAX_BYTES:raise ValueError('Thème trop volumineux (12 Mo maximum)')
    incoming=record(package.get('theme'));assets=package.get('assets',{})
    if not isinstance(assets,dict) or len(assets)>2:raise ValueError('Assets invalides')
    refs=references([incoming]);decoded={};mapping={}
    if set(assets)!=refs:raise ValueError('Assets manquants ou non référencés')
    for ref,encoded in assets.items():
        if not UPLOAD.fullmatch(ref) or not isinstance(encoded,str):raise ValueError('Asset invalide')
        try:raw=base64.b64decode(encoded,validate=True)
        except (ValueError,binascii.Error) as exc:raise ValueError('Asset corrompu') from exc
        ext=ref.rsplit('.',1)[1]
        if not 0<len(raw)<=4*1024*1024 or not image_valid(raw,ext):raise ValueError('Image invalide (PNG/JPEG/WebP/GIF uniquement)')
        new='/uploads/'+str(uuid.uuid4())+'.'+ext;mapping[ref]=new;decoded[new]=raw
    incoming['tokens']={k:mapping.get(v,v) if isinstance(v,str) else v for k,v in incoming['tokens'].items()}
    written=[]
    try:
        for ref,raw in decoded.items():
            target=uploads/ref[9:];target.write_bytes(raw);written.append(target)
        return save(db,{'theme':incoming},uploads)
    except Exception:
        for target in written:target.unlink(missing_ok=True)
        raise

def validate_backup(settings):
    rows=json.loads(settings.get('appearance.themes','[]'));active=settings.get('appearance.active',ORIGINAL)
    if not isinstance(rows,list) or len(rows)>3:raise ValueError('Maximum 3 thèmes personnalisés')
    clean=[record(row) for row in rows];ids=[x['id'] for x in clean]
    if len(set(ids))!=len(ids) or ORIGINAL in ids or any(not re.fullmatch(r'[a-f0-9-]{36}',i) for i in ids) or active not in [ORIGINAL,*ids]:raise ValueError('Identifiants de thèmes invalides')
    return clean
