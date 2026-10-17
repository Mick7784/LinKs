"""Instance configuration and admin authentication; no production defaults."""
import base64, hashlib, hmac, json, os, re, secrets, time
import storage
from pathlib import Path
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CONFIG_KEYS={'app.instance_id','appearance.themes','appearance.active','profile.name','profile.tagline','profile.description','profile.logo','profile.avatar',
 'footer.owner','site.url','app.timezone','app.setup_completed','app.config_schema_version',
 'admin.calendar_timed','admin.content_order','app.version','app.release_id','content.initialized','video.enabled','video.channel_id',
 'analytics.enabled','analytics.source_rules','analytics.metric_aliases','auth.mode'}
DEFAULTS={'admin.content_order':'["classic","video","highlight"]','profile.name':'Links','profile.tagline':'','profile.description':'','profile.logo':'',
 'profile.avatar':'','footer.owner':'','site.url':'','app.timezone':'UTC','video.enabled':'false',
 'video.channel_id':'','analytics.enabled':'false','analytics.source_rules':'[]',
 'analytics.metric_aliases':'{}','auth.mode':'local','app.setup_completed':'false',
 'app.config_schema_version':'1'}
PBKDF2_ROUNDS=600000
COOKIE='links_admin'
SESSION_SECONDS=8*60*60

def settings(db):return {r['key']:r['value'] for r in db.execute('SELECT * FROM settings')}
def get(db,key,default=''):return settings(db).get(key,default)
def put(db,key,value):db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,str(value)))
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def password_hash(value):
    if not isinstance(value,str) or not 12<=len(value)<=256:raise ValueError('Mot de passe : 12 à 256 caractères.')
    salt=secrets.token_bytes(24)
    result=hashlib.pbkdf2_hmac('sha256',value.encode(),salt,PBKDF2_ROUNDS)
    return 'pbkdf2-sha256$'+str(PBKDF2_ROUNDS)+'$'+salt.hex()+'$'+result.hex()
def password_ok(value,encoded):
    try:
        algorithm,rounds,salt,expected=encoded.split('$')
        if algorithm!='pbkdf2-sha256' or not 100000<=int(rounds)<=2000000 or not isinstance(value,str) or len(value)>256:return False
        result=hashlib.pbkdf2_hmac('sha256',value.encode(),bytes.fromhex(salt),int(rounds))
        return hmac.compare_digest(result.hex(),expected)
    except (ValueError,TypeError):return False
def account(db,username,password):
    if not isinstance(username,str) or not re.fullmatch(r'[\w.@+-]{3,80}',username):raise ValueError('Identifiant : 3 à 80 caractères, sans espaces.')
    encoded=password_hash(password)
    db.execute('INSERT INTO admin_accounts VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET username=excluded.username,password_hash=excluded.password_hash',(username,encoded))
    db.execute('DELETE FROM admin_sessions')

def site_url(value,allow_empty=False):
    if allow_empty and value=='':return ''
    if not isinstance(value,str) or len(value)>2048:raise ValueError('Adresse publique invalide.')
    p=urlsplit(value)
    try:port=p.port
    except ValueError:raise ValueError('Adresse publique invalide.')
    if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in {'','/'}:raise ValueError('Adresse publique : origine HTTP(S), sans chemin ni paramètres.')
    return value.rstrip('/')
def timezone_name(value):
    if not isinstance(value,str) or len(value)>100:raise ValueError('Fuseau horaire invalide.')
    try:ZoneInfo(value)
    except (ValueError,ZoneInfoNotFoundError):raise ValueError('Fuseau horaire inconnu.')
    return value
def source_rules(value):
    rules=json.loads(value) if isinstance(value,str) else value
    if not isinstance(rules,list) or len(rules)>30:raise ValueError('Règles de sources invalides.')
    for r in rules:
        if not isinstance(r,dict) or set(r)!={'key','label','aliases','domains'}:raise ValueError('Structure des sources invalide.')
        if any(not isinstance(r[k],str) or not r[k] or len(r[k])>120 for k in ['key','label']):raise ValueError('Source invalide.')
        if not re.fullmatch(r'[a-z0-9._-]+',r['key']):raise ValueError('Clé de source invalide.')
        for k in ['aliases','domains']:
            if not isinstance(r[k],list) or len(r[k])>20 or any(not isinstance(x,str) or not re.fullmatch(r'[a-z0-9._-]{1,120}',x) for x in r[k]):raise ValueError('Règle de source invalide.')
    if len({r['key'] for r in rules})!=len(rules):raise ValueError('Clés de sources en double.')
    return json.dumps(rules,ensure_ascii=False)

def initialize(db,legacy,config,asset_dirs,data_dir):
    """Add configuration before seeding. Never infer legacy from newly seeded rows."""
    db.execute('CREATE TABLE IF NOT EXISTS admin_accounts(id INTEGER PRIMARY KEY CHECK(id=1),username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS admin_sessions(token_hash TEXT PRIMARY KEY,csrf TEXT NOT NULL,expires INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS auth_state(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    values=settings(db)
    if 'app.config_schema_version' in values:return
    if legacy:
        manifest=Path(data_dir)/'legacy-instance.json'
        saved=json.loads(manifest.read_text()) if manifest.exists() else {}
        old=saved.get('config',config)
        profile=old.get('profile',{})
        for k in ['name','tagline','description','logo','avatar']:
            if 'profile.'+k not in values:put(db,'profile.'+k,profile.get(k,''))
        values=settings(db)
        # Uploaded assets already live in persistent storage. Legacy /assets URLs
        # remain valid through a dedicated persistent asset route.
        refs={values.get('profile.logo',''),values.get('profile.avatar','')}
        refs.update(r[0] for r in db.execute('SELECT image FROM content_blocks'))
        stored=Path(data_dir)/'assets';stored.mkdir(parents=True,exist_ok=True)
        for ref in refs:
            if not ref.startswith('/assets/'):continue
            name=ref[8:]
            if not re.fullmatch(r'[A-Za-z0-9._-]+',name):raise ValueError('Asset historique invalide.')
            target=stored/name
            if target.exists():continue
            candidates=[Path(p)/name for p in asset_dirs]
            origin=next((p for p in candidates if p.is_file()),None)
            if not origin:raise RuntimeError('Migration interrompue : asset historique manquant. Exécuter preserve-instance.py sur l’ancienne image avant la mise à jour.')
            storage.write(target,origin.read_bytes())
        aliases=saved.get('metric_aliases',{})
        if not aliases:
            for collection,prefix,idprefix,label in [('links','block:','legacy-link-','title'),('socials','button:','legacy-button-','label')]:
                for i,item in enumerate(old.get(collection,[])):
                    name=item.get(label,item.get('platform',''))
                    if name:aliases[('Réseau · ' if collection=='socials' else '')+name]=prefix+idprefix+str(i)
        inferred={**DEFAULTS,'footer.owner':values.get('profile.name',''),'site.url':saved.get('site_url') or os.environ.get('ANALYTICS_ORIGIN') or old.get('siteUrl',''),
          'app.timezone':saved.get('timezone','Europe/Paris'),'analytics.enabled':saved.get('analytics_enabled',os.environ.get('ANALYTICS_ENABLED','true')),
          'analytics.metric_aliases':json.dumps(aliases,ensure_ascii=False),'analytics.source_rules':source_rules(saved.get('source_rules',[])),
          'video.enabled':'true' if old.get('latestVideo') else 'false','video.channel_id':old.get('latestVideo',{}).get('channelId',''),
          'auth.mode':'external','app.setup_completed':'true'}
        if not inferred['site.url']:raise RuntimeError('Migration interrompue : adresse publique absente du transfert historique.')
    else:inferred=DEFAULTS
    for key,value in inferred.items():db.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(key,value))
    if not legacy:
        code=secrets.token_urlsafe(32)
        target=Path(data_dir)/'setup-code'
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as output:output.write(code+'\n')
        db.execute('INSERT OR REPLACE INTO auth_state VALUES(?,?)',('bootstrap_hash',digest(code)))
        print('Links : code de configuration initiale : '+code,flush=True)

def session(db,headers):
    cookie=SimpleCookie()
    try:cookie.load(headers.get('Cookie',''))
    except Exception:return None
    token=cookie.get(COOKIE)
    if not token or len(token.value)>100:return None
    return db.execute('SELECT * FROM admin_sessions WHERE token_hash=? AND expires>?',(digest(token.value),int(time.time()))).fetchone()
def new_session(db):
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);expires=int(time.time())+SESSION_SECONDS
    db.execute('DELETE FROM admin_sessions WHERE expires<=?',(int(time.time()),))
    db.execute('INSERT INTO admin_sessions VALUES(?,?,?)',(digest(token),csrf,expires))
    return token
def cookie_header(token,secure=False,clear=False):
    return COOKIE+'='+token+'; Path=/; HttpOnly; SameSite=Strict; Max-Age='+('0' if clear else str(SESSION_SECONDS))+('; Secure' if secure else '')
