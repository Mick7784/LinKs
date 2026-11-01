"""Small SQLite content manager and aggregate analytics service."""
import base64, binascii, copy, json, mimetypes, os, re, secrets, sqlite3, threading, uuid, sys, time, shutil
from contextlib import contextmanager, closing
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
import instance
import youtube
import themes
import images as user_images
import storage
import tracked_links
import tracked_batch
import descriptions
import affiliate_partners
import affiliation
import short_urls
import url_inspection
import pulse_manager
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent
if not (ROOT/"links.json").exists(): ROOT=ROOT.parent
DB=os.environ.get("ANALYTICS_DB","/data/analytics.db")
ORIGIN=os.environ.get("ANALYTICS_ORIGIN","").rstrip("/")
ADMIN=ROOT/"admin"; UPLOADS=Path(os.environ.get("UPLOAD_DIR","/data/uploads"))
CONFIG=json.loads((ROOT/"links.json").read_text(encoding="utf-8"))
DATA_LOCK=threading.RLock()
CAMPAIGN_WAKE=threading.Event()
CAMPAIGN_POLL_SECONDS=30
PARIS=ZoneInfo("UTC")
DATA_DIR=Path(DB).parent
STATIC=ROOT/"site" if (ROOT/"site").exists() else Path("/usr/share/nginx/html")
AUTH_ATTEMPTS=[]
AUTH_LOCK=threading.Lock()
TYPES={"classic","promo","featured"}; ICONS={"youtube","instagram","tiktok","discord","mail","website","cart","home","amazon","facebook","x","linkedin","github","threads","twitch","telegram","whatsapp","pinterest","reddit","snapchat","network","contact","link"}
BADGES={"","Promo","Nouveau","Partenaire","Bon plan"}
ICONS.update({'phone','video','podcast','blog','download','calendar','location','homeassistant','email','tag'})
IMAGE_TYPES={"image/jpeg":".jpg","image/png":".png","image/webp":".webp","image/gif":".gif"}

@contextmanager
def connection():
    with DATA_LOCK:
        db=sqlite3.connect(DB,timeout=10); db.row_factory=sqlite3.Row; db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
def now_iso(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def instant(value,strict=False,zone=None):
    if not value:return None
    if not isinstance(value,str):raise ValueError("Date invalide")
    zone=zone or PARIS
    try:
        result=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
    except ValueError as exc: raise ValueError("Date invalide") from exc
    if strict and result.tzinfo is None:
        # A local wall time at a DST transition needs an explicit offset.
        candidates={local.astimezone(timezone.utc) for fold in (0,1)
                    for local in [result.replace(tzinfo=zone,fold=fold)]
                    if local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)==result}
        if len(candidates)!=1:raise ValueError("Heure locale ambiguë ou inexistante : préciser le décalage UTC")
    return (result if result.tzinfo else result.replace(tzinfo=zone)).astimezone(timezone.utc)
def init():
    global ORIGIN,PARIS
    Path(DB).parent.mkdir(parents=True,exist_ok=True); UPLOADS.mkdir(parents=True,exist_ok=True)
    with DATA_LOCK:
        affiliation.migration_backup(DB)
        category_backup=tracked_links.remove_legacy_category(DB)
    if category_backup:
        print('LinKs : catégories supprimées ; sauvegarde SQLite vérifiée : '+str(category_backup),flush=True)
    existed=Path(DB).exists() and Path(DB).stat().st_size>0
    if existed:
        with closing(sqlite3.connect(DB)) as before:
            tables={r[0] for r in before.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'content_blocks' in tables and 'retired' not in {r[1] for r in before.execute('PRAGMA table_info(content_blocks)')}:
                target=DATA_DIR/'pre-v1310-database.db'
                if not target.exists():
                    with closing(sqlite3.connect(target)) as backup:before.backup(backup)
            legacy="settings" in tables and not before.execute("SELECT 1 FROM settings WHERE key='app.config_schema_version'").fetchone()
            if legacy:
                target=DATA_DIR/"pre-v11-database.db"
                if not target.exists():
                    with closing(sqlite3.connect(target)) as backup:before.backup(backup)
    else:legacy=False
    with connection() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS counts(day TEXT,source TEXT,kind TEXT,link TEXT,total INTEGER NOT NULL,PRIMARY KEY(day,source,kind,link))")
        db.execute("""CREATE TABLE IF NOT EXISTS content_blocks(
          id TEXT PRIMARY KEY,type TEXT NOT NULL,internal_name TEXT NOT NULL,title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',url TEXT NOT NULL,icon TEXT NOT NULL DEFAULT 'website',
          image TEXT NOT NULL DEFAULT '',badge TEXT NOT NULL DEFAULT '',cta TEXT NOT NULL DEFAULT '',
          position INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1,draft INTEGER NOT NULL DEFAULT 0,
          start_at TEXT,end_at TEXT,archived INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
          priority TEXT NOT NULL DEFAULT 'normal')""")
        if "priority" not in {row[1] for row in db.execute("PRAGMA table_info(content_blocks)")}:
            db.execute("ALTER TABLE content_blocks ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'")
        if "promo_code" not in {row[1] for row in db.execute("PRAGMA table_info(content_blocks)")}:
            db.execute("ALTER TABLE content_blocks ADD COLUMN promo_code TEXT NOT NULL DEFAULT ''")
        db.execute("""CREATE TABLE IF NOT EXISTS top_buttons(
          id TEXT PRIMARY KEY,icon TEXT NOT NULL,label TEXT NOT NULL,url TEXT NOT NULL,position INTEGER NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
        if "custom_icon" not in {row[1] for row in db.execute("PRAGMA table_info(top_buttons)")}:
            db.execute("ALTER TABLE top_buttons ADD COLUMN custom_icon TEXT NOT NULL DEFAULT ''")
        for table in ('content_blocks','top_buttons'):
            if 'retired' not in {row[1] for row in db.execute('PRAGMA table_info('+table+')')}:
                db.execute('ALTER TABLE '+table+' ADD COLUMN retired INTEGER NOT NULL DEFAULT 0 CHECK(retired IN (0,1))')
        db.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        db.execute("""CREATE TABLE IF NOT EXISTS story_links(
          token TEXT PRIMARY KEY,promotion_id TEXT NOT NULL UNIQUE,name TEXT NOT NULL,
          created_at TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0)""")
        db.execute("CREATE TABLE IF NOT EXISTS footer_quotes(id TEXT PRIMARY KEY,text TEXT NOT NULL UNIQUE,active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),created_at TEXT NOT NULL)")
        tracked_links.initialize(db)
        affiliate_partners.initialize(db)
        affiliation.initialize(db)
        short_urls.initialize(db)
        descriptions.initialize(db)
        instance.initialize(db,legacy,CONFIG,[DATA_DIR/"assets",STATIC/"assets"],DATA_DIR)
        db.execute("INSERT OR IGNORE INTO settings VALUES('app.instance_id',?)",(uuid.uuid4().hex,))
        themes.initialize(db)
        storage.initialize(db)
        # Archives and retired rows continue owning their images and metric identity.
        init_version(db)
        ORIGIN=instance.site_url(instance.get(db,"site.url"),allow_empty=True)
        PARIS=ZoneInfo(instance.get(db,"app.timezone","UTC"))
        storage.scan(db,UPLOADS,assets=DATA_DIR/'assets',system_assets=STATIC/'assets')

def checked_version(value):
    if not isinstance(value,str) or not re.fullmatch(r"V[0-9]+\.[0-9]+(?:\.[0-9]+)?",value) or len(value)>40:
        raise ValueError("Format attendu : V1.4.1, V1.201 ou V2.1")
    return value

def software_version():
    return checked_version(os.environ.get("APP_RELEASE_VERSION") or (ROOT/"VERSION").read_text().strip())

def init_version(db):
    release=software_version()
    release_id=os.environ.get("APP_RELEASE_ID") or "bundled:"+release
    for key,value in [('app.version',release),('app.release_id',release_id)]:
        db.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,value))

def storage_state(action='scan'):
    with connection() as db:return storage.scan(db,UPLOADS,action,assets=DATA_DIR/'assets',system_assets=STATIC/'assets')

def storage_worker():
    while True:
        time.sleep(3600)
        try:storage_state('cleanup')
        except (OSError,sqlite3.Error,ValueError):print('Links : nettoyage automatique temporairement indisponible.',flush=True)

def analytics_enabled():
    with connection() as db:return instance.get(db,"analytics.enabled")=="true"

def sync_configuration(db):
    global ORIGIN,PARIS
    ORIGIN=instance.site_url(instance.get(db,"site.url"),allow_empty=True);PARIS=ZoneInfo(instance.get(db,"app.timezone","UTC"))

def record_promo_copy(data):
    if not analytics_enabled():return
    key=data.get("link","")
    code=data.get("code")
    if not isinstance(key,str) or not key.startswith("block:") or not isinstance(code,str) or not code.strip() or len(code)>80:raise ValueError()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT id,internal_name,type FROM content_blocks WHERE id=?",(key[6:],)).fetchone()
        if not row or row["type"] not in {"promo","featured"}:raise ValueError()
        stamp=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0).isoformat()
        snapshot=json.dumps({"id":row["id"],"name":row["internal_name"],"code":code,"timestamp":stamp},sort_keys=True,ensure_ascii=False)
        increment(db,"promo_code_copy",source_of(data),snapshot,datetime.now(PARIS).date().isoformat())

def record(kind,source,link,day=None,validate=False):
    if not analytics_enabled():return
    day=day or datetime.now(PARIS).date().isoformat()
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        # Validation and collection share the cleanup's SQLite write lock. A
        # successful request cannot leave a metric pointing to a deleted row.
        if validate and kind in {'click','impression'} and not valid_metric(link,db):raise ValueError()
        increment(db,kind,source,link,day)
def increment(db,kind,source,link,day):
    db.execute("INSERT INTO counts VALUES(?,?,?,?,1) ON CONFLICT(day,source,kind,link) DO UPDATE SET total=total+1",(day,source,kind,link))
    # The report window is bounded; recording a new action never purges history.

def collection_allowed(headers):
    if headers.get('DNT')=='1' or headers.get('Sec-GPC')=='1':return False
    agent=headers.get('User-Agent','').lower()
    return not any(x in agent for x in ['bot','spider','crawler','headless','facebookexternalhit','meta-externalagent','preview'])
def source_of(data):
    source=data.get("source","")
    if not isinstance(source,str):raise ValueError()
    source=source.strip().lower()
    known={"yt","ig","youtube","instagram","facebook","tiktok","discord","google","newsletter","site","mail","qr"}
    with connection() as db:rules=json.loads(instance.get(db,"analytics.source_rules","[]"))
    if source:
        for rule in rules:
            if source==rule["key"] or source in rule["aliases"]:return rule["key"]
        return {"yt":"youtube","ig":"instagram"}.get(source,source) if source in known else "autre-campagne"
    ref=data.get("referrer","")
    if not isinstance(ref,str):raise ValueError()
    host=(urlsplit(ref).hostname or "").lower()
    if host==urlsplit(ORIGIN).hostname:return "direct-inconnu"
    for domain,name in [("youtube.com","youtube"),("youtu.be","youtube"),("instagram.com","instagram"),("facebook.com","facebook"),("tiktok.com","tiktok"),("discord.com","discord"),("google.com","google"),("google.fr","google")]:
        if host==domain or host.endswith("."+domain):return name
    for rule in rules:
        if any(host==domain or host.endswith("."+domain) for domain in rule["domains"]):return rule["key"]
    return "autre-site" if host else "direct-inconnu"
def metric_aliases(db):
    saved=json.loads(instance.get(db,"analytics.metric_aliases","{}"))
    existing={"block:"+r[0] for r in db.execute("SELECT id FROM content_blocks")}|{"button:"+r[0] for r in db.execute("SELECT id FROM top_buttons")}
    return {name:key for name,key in saved.items() if key in existing}

def source_labels(db):
    """Display metadata only; never rewrite event keys or infer an identity from a name."""
    rules=json.loads(instance.get(db,'analytics.source_rules','[]'))
    labels={rule['key']:rule['label'] for rule in rules}
    aliases={}
    for rule in rules:
        for alias in rule['aliases']:aliases.setdefault(alias,set()).add(rule['key'])
    for alias,keys in aliases.items():
        if alias not in labels and len(keys)==1:labels[alias]=labels[next(iter(keys))]
    labels.update({'tracked:'+row['id']:row['name'] for row in db.execute('SELECT id,name FROM tracking_sources')})
    return labels

def report(start,end,source=""):
    a,b=date.fromisoformat(start),date.fromisoformat(end)
    if a>b or (b-a).days>399:raise ValueError("Période maximale : 400 jours")
    where="day BETWEEN ? AND ? AND kind IN ('view','click')"; params=[start,end]
    if source:where+=" AND source=?";params.append(source)
    with connection() as db:
        rows=[dict(r) for r in db.execute("SELECT * FROM counts WHERE "+where+" ORDER BY day",params)]
        labels={"block:"+r["id"]:r["title"] for r in db.execute("SELECT id,title FROM content_blocks")}
        labels.update({"button:"+r["id"]:r["label"] for r in db.execute("SELECT id,label FROM top_buttons")})
        labels["latest-video"]="Dernière vidéo"
        aliases=metric_aliases(db)
        for row in rows:
            if row["kind"]=="click":row["link"]=aliases.get(row["link"],row["link"])
            row["label"]=labels.get(row["link"], "Ancien lien" if row["link"].startswith(("block:","button:")) else row["link"])
        story_where="c.day BETWEEN ? AND ? AND c.kind='story'";story_params=[start,end]
        if source:story_where+=" AND c.source=?";story_params.append(source)
        stories=[dict(r) for r in db.execute("""SELECT c.day,c.total,c.source,c.link,
          s.promotion_id,s.token,COALESCE(b.internal_name,s.name) label
          FROM counts c JOIN story_links s ON substr(c.link,7,length(s.token))=s.token
          LEFT JOIN content_blocks b ON b.id=s.promotion_id
          WHERE """+story_where+" ORDER BY c.day",story_params)]
        for row in stories:row['hour']=row.pop('link').rsplit(':',1)[-1]
        metric_where="day BETWEEN ? AND ? AND kind IN ('impression','click','promo_code_copy')";metric_params=[start,end]
        if source:metric_where+=" AND source=?";metric_params.append(source)
        copies=[];campaign_metrics=[]
        for metric in db.execute("SELECT * FROM counts WHERE "+metric_where,metric_params):
            if metric["kind"]=="promo_code_copy":
                snapshot=json.loads(metric["link"])
                copies.append({"day":metric["day"],"source":metric["source"],"total":metric["total"],**snapshot})
            elif metric["link"].startswith("block:"):
                campaign_metrics.append({"day":metric["day"],"source":metric["source"],"id":metric["link"][6:],"kind":metric["kind"],"total":metric["total"]})
        tracked=tracked_links.tracked_events(db,start,end,source)
        source_names=source_labels(db)
        # Legacy shared keys have a captured identity. Public traffic with the same
        # key still describes a generic referrer, not a publication placement.
        shared_names={row['key']:row['name'] for row in db.execute('''SELECT k.key,s.name
            FROM tracking_source_keys k JOIN tracking_sources s ON s.id=k.source_id
            WHERE k.key NOT IN ('instagram-story','shared-unknown')''')}
        for row in stories:
            row['source_name']=source_names.get(row['source'],shared_names.get(row['source']))
    return {"rows":rows,"stories":stories,"tracked":tracked,"source_names":source_names,"promo_code_copies":copies,"campaign_metrics":campaign_metrics,"timezone":str(PARIS)}

STORY_TOKEN=re.compile(r'st_[A-Za-z0-9_-]{16}')
def story_url_valid(url):
    if not isinstance(url,str) or any(ord(c)<=32 for c in url) or '\\' in url:return False
    try:
        parsed=urlsplit(url)
        parsed.port
        parsed.hostname.encode('idna') if parsed.hostname else None
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:return False
        # Do not allow a tracked redirect to point back into this application.
        return parsed.hostname.lower().rstrip('.')!=(urlsplit(ORIGIN).hostname or '').lower().rstrip('.')
    except (ValueError,UnicodeError):return False

def story_destination(url):
    parsed=urlsplit(url)
    host=parsed.hostname.encode('idna').decode('ascii')
    if ':' in host:host='['+host+']'
    netloc=host+(':'+str(parsed.port) if parsed.port is not None else '')
    return urlunsplit((parsed.scheme,netloc,quote(parsed.path,safe="/%:@!$&'()*+,;=-._~"),quote(parsed.query,safe="%/?@:!$&'()*+,;=-._~"),quote(parsed.fragment,safe="%/?@:!$&'()*+,;=-._~")))

def story_link(promotion_id,source=None):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        item=db.execute("SELECT * FROM content_blocks WHERE id=? AND type IN ('promo','featured')",(promotion_id,)).fetchone()
        if not item:raise ValueError('Promotion introuvable')
        if not story_url_valid(item['url']):raise ValueError('URL partenaire HTTP(S) valide requise')
        link=db.execute('SELECT * FROM story_links WHERE promotion_id=?',(promotion_id,)).fetchone()
        if not link:
            for _ in range(5):
                token='st_'+secrets.token_urlsafe(12)
                try:db.execute('INSERT INTO story_links VALUES(?,?,?,?,0)',(token,promotion_id,item['internal_name'],now_iso()));break
                except sqlite3.IntegrityError:continue
            else:raise ValueError('Impossible de générer le lien Story')
            link=db.execute('SELECT * FROM story_links WHERE promotion_id=?',(promotion_id,)).fetchone()
        if source is not None:
            channel=short_urls.campaign_source(db,source)
            return short_urls.get_or_create(db,link['token'],channel,ORIGIN,now_iso())
        return {'url':ORIGIN+'/go/'+link['token']}

def profile(db):
    values=instance.settings(db)
    return {**{k:values.get("profile."+k,"") for k in ["name","tagline","description","avatar","logo"]},
      "content_order":json.loads(values.get("admin.content_order",'["classic","video","highlight"]')),
      "app_version":software_version(),"footer_owner":values.get("footer.owner",values.get("profile.name","")),
      "site_url":values.get("site.url",""),"timezone":values.get("app.timezone","UTC"),
      "analytics_enabled":values.get("analytics.enabled")=="true","video_enabled":values.get("video.enabled")=="true",
      "video_channel_id":values.get("video.channel_id",""),"auth_mode":values.get("auth.mode","local"),
      "setup_completed":values.get("app.setup_completed")=="true","source_rules":json.loads(values.get("analytics.source_rules","[]"))}
def status_of(row,at=None):
    if row["archived"]:return "Archivé"
    if row["draft"]:return "Brouillon"
    if not row["active"]:return "Désactivé"
    at=at or datetime.now(timezone.utc); start=instant(row["start_at"]); end=instant(row["end_at"])
    if start and start>at:return "Programmé"
    if end and end<=at:return "Expiré"
    return "Actif"
def serialize(row,totals=None,at=None):
    item=dict(row); item.update(active=bool(item["active"]),draft=bool(item["draft"]),archived=bool(item["archived"]),status=status_of(row,at))
    if totals is not None:
        item["clicks"]=totals.get(("click","block:"+item["id"]),0)
        item["impressions"]=totals.get(("impression","block:"+item["id"]),0)
        item["ctr"]=round(item["clicks"]*100/item["impressions"],1) if item["impressions"] else None
    return item
def totals(db):
    aliases=metric_aliases(db); result={}
    for row in db.execute("SELECT kind,link,SUM(total) total FROM counts WHERE kind IN ('click','impression') GROUP BY kind,link"):
        link=aliases.get(row["link"],row["link"]) if row["kind"]=="click" else row["link"]
        key=(row["kind"],link); result[key]=result.get(key,0)+row["total"]
    return result
def content_list(archived=False):
    with connection() as db:
        now=datetime.now(timezone.utc)
        rows=list(db.execute("SELECT * FROM content_blocks ORDER BY CASE WHEN type IN ('promo','featured') THEN 0 ELSE 1 END,position,created_at,id"))
        states={item['id']:item for item in select_campaigns(rows,now)['items']}
        rows=sorted((r for r in rows if r['type'] in CAMPAIGN_TYPES),key=campaign_order)+[r for r in rows if r['type'] not in CAMPAIGN_TYPES]
        clicks=totals(db);timed=json.loads(instance.get(db,"admin.calendar_timed") or "[]")
        return [{**serialize(r,clicks,now),**states.get(r['id'],{}),"calendar_timed":r['id'] in timed,**(affiliate_partners.campaign_metadata(db,r['id'],r['url']) if r['type'] in CAMPAIGN_TYPES else {})} for r in rows if bool(r['archived'])==archived]


CAMPAIGN_TYPES={'promo','featured'}
CAMPAIGN_LIMIT=3
CAMPAIGN_FALLBACK='/assets/link-shopping.webp'

def campaign_image_value(value):
    if not isinstance(value,str) or (value and not re.fullmatch(r'/uploads/[a-f0-9-]{36}\.(png|jpg|webp)',value)):
        raise ValueError('Importer un visuel PNG, JPEG ou WebP de cette installation')
    return value

def campaign_image_settings(db):
    value=instance.get(db,'appearance.campaign_image','')
    return {'image':value,'fallback':CAMPAIGN_FALLBACK,'resolved_image':value or CAMPAIGN_FALLBACK}

def save_campaign_image(data):
    value=campaign_image_value(data.get('image',''))
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        storage.require_file(UPLOADS,value,db)
        if value:user_images.validate((UPLOADS/value[9:]).read_bytes(),Path(value).suffix)
        instance.put(db,'appearance.campaign_image',value)
        return campaign_image_settings(db)

def campaign_duration(row):
    # Preserve open historical intervals and visual types, especially featured.
    return 'one_off' if row['end_at'] else 'permanent'

def campaign_order(row):
    # position is appended on creation and persisted by the existing reorder API.
    # The old high/normal editorial priority never overrides duration or order.
    return (campaign_duration(row)!='one_off',row['position'],instant(row['created_at']),row['id'])

def select_campaigns(rows,at=None):
    """Read-only selection at one instant; eligibility is independent of capacity."""
    at=instant(at,strict=True) if isinstance(at,str) else at or datetime.now(timezone.utc)
    if at.tzinfo is None:raise ValueError('Préciser le fuseau de la date de sélection')
    at=at.astimezone(timezone.utc)
    items=[];eligible=[]
    for row in sorted((r for r in rows if r['type'] in CAMPAIGN_TYPES),key=campaign_order):
        state=('retired' if row['retired'] else {'Archivé':'archived','Brouillon':'draft',
               'Désactivé':'disabled','Programmé':'scheduled','Expiré':'ended','Actif':'eligible'}[status_of(row,at)])
        is_eligible=state=='eligible'
        if is_eligible:
            eligible.append(row['id'])
            state='visible' if len(eligible)<=CAMPAIGN_LIMIT else 'waiting'
        items.append({'id':row['id'],'title':row['title'],'duration_type':campaign_duration(row),'selection_state':state,
                      'eligible':is_eligible,'visible':state=='visible'})
    return {'at':at.isoformat().replace('+00:00','Z'),'limit':CAMPAIGN_LIMIT,'items':items,
            'eligible_ids':eligible,'visible_ids':eligible[:CAMPAIGN_LIMIT],'waiting_ids':eligible[CAMPAIGN_LIMIT:]}

def campaign_selection(at=None):
    with connection() as db:return select_campaigns(list(db.execute('SELECT * FROM content_blocks')),at)


def campaign_references(db):
    """All lifetime metric identities and published references, without a date filter."""
    retained={r[0] for r in db.execute('SELECT promotion_id FROM story_links')}
    aliases=json.loads(instance.get(db,'analytics.metric_aliases','{}'))
    retained.update(value[6:] for value in aliases.values() if value.startswith('block:'))
    for metric in db.execute('SELECT DISTINCT kind,link FROM counts'):
        key=aliases.get(metric['link'],metric['link'])
        if key.startswith('block:'):retained.add(key[6:])
        if metric['kind']=='promo_code_copy':
            snapshot=json.loads(metric['link'])
            if not isinstance(snapshot,dict) or not isinstance(snapshot.get('id'),str):
                raise ValueError('Historique de copie illisible : nettoyage suspendu')
            retained.add(snapshot['id'])
    # Also honor declared incoming references, including ON DELETE CASCADE:
    # cleanup must preserve their owner instead of implicitly deleting children.
    def quoted(name):return '"'+name.replace('"','""')+'"'
    for table in list(db.execute("SELECT name FROM sqlite_master WHERE type='table'")):
        if table['name']=='campaign_partners':continue  # Owned provenance, cascaded only for truly unused campaigns.
        for reference in db.execute('PRAGMA foreign_key_list('+quoted(table['name'])+')'):
            if reference['table']=='content_blocks' and reference['to'] in (None,'id'):
                retained.update(r[0] for r in db.execute('SELECT '+quoted(reference['from'])+' FROM '+quoted(table['name'])))
    # story_links protects both the long redirect and every short alias pointing
    # to it, including zero-click, deleted or revoked historical publications.
    return retained


def cleanup_campaigns(at=None):
    """Archive expired campaigns with history/references; delete only unused ones.

    Never unlink media here. Existing reference-aware storage maintenance gives
    newly orphaned files its normal grace period and protects shared images.
    """
    result={'archived_ids':[],'deleted_ids':[],'skipped_ids':[],'next_delay':CAMPAIGN_POLL_SECONDS}
    with DATA_LOCK:
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            zone=ZoneInfo(instance.get(db,'app.timezone','UTC'))
            now=instant(at,strict=True,zone=zone) if isinstance(at,str) else at or datetime.now(timezone.utc)
            if now.tzinfo is None:raise ValueError('Préciser le fuseau de la date de nettoyage')
            now=now.astimezone(timezone.utc);expired=[]
            rows=db.execute("""SELECT id,end_at FROM content_blocks WHERE type IN ('promo','featured')
                               AND end_at IS NOT NULL AND end_at!='' AND archived=0 AND retired=0 AND draft=0
                               ORDER BY id""")
            for row in rows:
                try:end=instant(row['end_at'],zone=zone)
                except ValueError:
                    result['skipped_ids'].append(row['id']);continue
                if end<=now:expired.append(row['id'])
                else:result['next_delay']=min(result['next_delay'],(end-now).total_seconds())
            if expired:
                retained=campaign_references(db)
                stamp=now.isoformat().replace('+00:00','Z')
                for ident in expired:
                    if ident in retained:
                        db.execute('UPDATE content_blocks SET archived=1,updated_at=? WHERE id=?',(stamp,ident))
                        result['archived_ids'].append(ident)
                    else:
                        db.execute('DELETE FROM content_blocks WHERE id=?',(ident,))
                        result['deleted_ids'].append(ident)
                if result['deleted_ids']:
                    timed=json.loads(instance.get(db,'admin.calendar_timed','[]'))
                    deleted=set(result['deleted_ids'])
                    updated=[ident for ident in timed if ident not in deleted]
                    if updated!=timed:instance.put(db,'admin.calendar_timed',json.dumps(updated))
        # Commit first, then refresh the existing public-only fallback atomically.
        # Retry even on an unchanged pass if an earlier file write had failed.
        write_public_fallback()
    return result


def campaign_worker(stop=None):
    stop=stop or threading.Event()
    while not stop.is_set():
        CAMPAIGN_WAKE.clear()
        try:delay=cleanup_campaigns()['next_delay']
        except (OSError,sqlite3.Error,ValueError,TypeError):
            print('Links : nettoyage des campagnes temporairement indisponible.',flush=True)
            delay=CAMPAIGN_POLL_SECONDS
        CAMPAIGN_WAKE.wait(max(.05,delay))


def button_list(archived=False):
    with connection() as db:
        clicks=totals(db); result=[]
        for row in db.execute("SELECT * FROM top_buttons WHERE retired=? ORDER BY position,created_at",(int(archived),)):
            item=dict(row);item["active"]=bool(item["active"]);item["clicks"]=clicks.get(("click","button:"+item["id"]),0);result.append(item)
        return result
PUBLIC_SECTIONS=['video','highlight','classic']

def public_section_order(db):
    return json.loads(instance.get(db,'public.section_order',json.dumps(PUBLIC_SECTIONS)))

def classic_priority_order(db):
    # Until the first explicit save, retain legacy public ordering exactly.
    return '' if instance.get(db,'public.section_order') else "CASE WHEN priority='high' THEN 0 ELSE 1 END,"

def page_layout(db):
    ids=[r['id'] for r in db.execute("SELECT id FROM content_blocks WHERE type='classic' AND archived=0 AND retired=0 ORDER BY "+classic_priority_order(db)+"position,created_at,id")]
    layout={'section_order':public_section_order(db),'link_ids':ids}
    return {**layout,'revision':instance.digest(json.dumps(layout,sort_keys=True))}

def save_page_layout(data):
    if not isinstance(data,dict) or set(data)!={'section_order','link_ids','revision'}:raise ValueError('Organisation invalide')
    validate_settings({'public.section_order':json.dumps(data['section_order'])})
    ids=data['link_ids']
    if not isinstance(ids,list) or any(not isinstance(x,str) for x in ids) or len(set(ids))!=len(ids):raise ValueError('Ordre des liens invalide')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current=page_layout(db)
        if data['revision']!=current['revision'] or set(ids)!=set(current['link_ids']):raise ValueError('Les contenus ont changé. Annulez pour recharger leur organisation avant d’enregistrer.')
        instance.put(db,'public.section_order',json.dumps(data['section_order']))
        for position,ident in enumerate(ids):
            db.execute('UPDATE content_blocks SET position=? WHERE id=?',(position,ident))
        return page_layout(db)

def public_config(snapshot=False):
    with connection() as db:
        now=datetime.now(timezone.utc)
        rows=list(db.execute("SELECT * FROM content_blocks WHERE retired=0 AND archived=0 ORDER BY CASE WHEN type IN ('promo','featured') THEN 0 ELSE 1 END,"+classic_priority_order(db)+"position,created_at,id"))
        selection=select_campaigns(rows,now)
        default_image=campaign_image_settings(db)['resolved_image']
        # Keep all eligible campaigns in links for existing PulSe consumers.
        # Only visible_campaign_ids is capped. Snapshot order also supports the
        # existing date-filtered static fallback through future slot changes.
        ordered=sorted((r for r in rows if r['type'] in CAMPAIGN_TYPES),key=campaign_order)+[r for r in rows if r['type'] not in CAMPAIGN_TYPES]
        blocks=[serialize(r,at=now) for r in ordered if snapshot or status_of(r,now)=="Actif"]
        if snapshot:blocks=[x for x in blocks if x['active'] and not x['draft']]
        quote=db.execute("SELECT text FROM footer_quotes WHERE active=1 ORDER BY " + ("created_at,id" if snapshot else "RANDOM()") + " LIMIT 1").fetchone()
        buttons=[dict(r) for r in db.execute("SELECT * FROM top_buttons WHERE active=1 AND retired=0 ORDER BY position,created_at")]
        result={"profile":profile(db),"socials":[{"id":x["id"],"platform":x["icon"],"custom_icon":x["custom_icon"],"label":x["label"],"url":x["url"],"metricKey":"button:"+x["id"]} for x in buttons],
                "links":[{"id":x["id"],"type":x["type"],"title":x["title"],"description":x["description"],"url":x["url"],"icon":x["icon"],"image":x["image"],"badge":x["badge"],"cta":x["cta"],"priority":x["priority"],"start_at":x["start_at"],"end_at":x["end_at"],"promo_code":x["promo_code"],"metricKey":"block:"+x["id"]} for x in blocks]}
        # Expose only the next public schedule boundary, never future private content.
        boundaries=[stamp for row in db.execute("SELECT start_at,end_at FROM content_blocks WHERE retired=0 AND archived=0 AND active=1 AND draft=0 AND type IN ('promo','featured')") for key in ("start_at","end_at") if (stamp:=instant(row[key])) and stamp>now]
        result["next_campaign_change"]=min(boundaries).isoformat().replace("+00:00","Z") if boundaries else None
        if not snapshot:result['visible_campaign_ids']=selection['visible_ids']
        result['campaign_default_image']=default_image
        for item in result['links']:
            if item['type'] in CAMPAIGN_TYPES:item['effective_image']=item['image'] or default_image
        result["section_order"]=public_section_order(db)
        result["appearance"]=themes.public(db)
        result["profile"]["footer_quote"]=quote["text"] if quote else ""
    if result["profile"]["video_enabled"]:result["latestVideo"]={"enabled":True}
    result["setup_completed"]=result["profile"]["setup_completed"]
    result["timezone"]=result["profile"]["timezone"]
    result["analytics_enabled"]=result["profile"]["analytics_enabled"]
    for key in ["auth_mode","source_rules","video_channel_id","content_order"]:result["profile"].pop(key,None)
    return result

def write_public_fallback():
    """Public-only snapshot for static fallback; never serialize private settings."""
    with DATA_LOCK:
        target=DATA_DIR/'public-fallback.json'
        payload=json.dumps(public_config(snapshot=True),ensure_ascii=False,sort_keys=True).encode('utf-8')
        if target.is_file() and target.read_bytes()==payload:return False
        storage.write(target,payload)
        return True


def quote_list():
    with connection() as db:
        return [dict(r,active=bool(r["active"])) for r in db.execute("SELECT * FROM footer_quotes ORDER BY created_at,id")]

def quote_entries(data):
    raw=data.get("text","")
    if not isinstance(raw,str) or len(raw)>1024*1024:raise ValueError("Texte invalide ou trop volumineux (1 Mo maximum)")
    entries=[s.strip() for s in ([raw] if data.get("single") is True else raw.split("|||") if "|||" in raw else raw.splitlines()) if s.strip()]
    if not entries:raise ValueError("Ajoute au moins une citation")
    if any(len(s)>1000 for s in entries):raise ValueError("Une citation dépasse 1 000 caractères")
    return entries

def add_quotes(data,preview=False):
    entries=quote_entries(data)
    with connection() as db:
        if not preview:db.execute("BEGIN IMMEDIATE")
        existing={r[0] for r in db.execute("SELECT text FROM footer_quotes")}
        new=list(dict.fromkeys(s for s in entries if s not in existing))
        available=max(0,300-len(existing))
        cap=data.get("limit",300)
        if type(cap) is not int or not 0<=cap<=300:raise ValueError("Limite invalide")
        allowed=min(len(new),available,cap)
        if not preview and data.get("single") is True and new and not available:raise ValueError("Limite de 300 citations atteinte.")
        if not preview:
            for value in new[:allowed]:
                db.execute("INSERT INTO footer_quotes VALUES(?,?,1,?)",(str(uuid.uuid4()),value,now_iso()))
        return {"detected":len(entries),"new":len(new),"duplicates":len(entries)-len(new),"allowed":allowed,"excess":len(new)-allowed,"added":0 if preview else allowed}

def required(data,key,limit=300):
    value=data.get(key,"")
    if not isinstance(value,str) or not value.strip() or len(value.strip())>limit:raise ValueError(f"{key} est obligatoire")
    return value.strip()
def optional(data,key,limit=1000):
    value=data.get(key,"")
    if value is None:return ""
    if not isinstance(value,str) or len(value.strip())>limit:raise ValueError(f"{key} est invalide")
    return value.strip()
def valid_url(value):
    if not isinstance(value,str) or len(value)>2000:return False
    parsed=urlsplit(value);return parsed.scheme in {"http","https","mailto","tel"} and bool(parsed.netloc or parsed.path)
def supported_image(value):
    if not value:return True
    if value.startswith("system:"):return value[7:] in themes.BACKGROUNDS
    if re.fullmatch(r"/(uploads|assets)/[A-Za-z0-9._-]+",value):return True
    try:
        parsed=urlsplit(value)
        return parsed.scheme=="https" and parsed.netloc=="i.ytimg.com" and not parsed.username and not parsed.password
    except ValueError:return False

def block_data(data,allow_legacy_image=False):
    kind=data.get("type","classic")
    if kind in CAMPAIGN_TYPES and not data.get('internal_name'):data={**data,'internal_name':data.get('title','')}
    if "calendar_timed" in data and not isinstance(data["calendar_timed"],bool):raise ValueError("Mode horaire invalide")
    if kind not in TYPES:raise ValueError("Type invalide")
    url=required(data,"url",2000)
    if not valid_url(url):raise ValueError("URL invalide")
    icon=data.get("icon","website"); badge=optional(data,"badge",40); image=optional(data,"image",2000); priority=data.get("priority","normal")
    if icon not in ICONS:icon="website"
    if badge not in BADGES:raise ValueError("Badge invalide")
    if priority not in {"normal","high"}:raise ValueError("Priorité invalide")
    if image.startswith("system:") and image[7:] not in themes.BACKGROUNDS:raise ValueError("Fond système inconnu")
    remote=urlsplit(image) if image else None
    campaign_remote=kind in CAMPAIGN_TYPES and remote and remote.scheme=='https' and remote.hostname and not remote.username and not remote.password and not any(ord(c)<=32 or c=='\\' for c in image)
    if image and not supported_image(image) and not campaign_remote and not (allow_legacy_image and valid_url(image)):raise ValueError("Image non prise en charge : importer une image locale ou choisir une URL HTTPS pour une campagne")
    start,end=instant(data.get("start_at"),strict=not allow_legacy_image),instant(data.get("end_at"),strict=not allow_legacy_image)
    if start and end and end<=start:raise ValueError("La fin doit suivre le début")
    return {**({"calendar_timed":data["calendar_timed"]} if "calendar_timed" in data else {}),"type":kind,"internal_name":required(data,"internal_name"),"title":required(data,"title"),"description":optional(data,"description"),"url":url,"icon":icon,"image":image,"badge":badge,"cta":optional(data,"cta",80),**({"promo_code":optional(data,"promo_code",80)} if "promo_code" in data else {}),"priority":priority,"active":1 if data.get("active",True) else 0,"draft":1 if data.get("draft",False) else 0,"start_at":start.isoformat().replace("+00:00","Z") if start else None,"end_at":end.isoformat().replace("+00:00","Z") if end else None}
def promotion_rows(db,exclude_id=None):
    query="SELECT * FROM content_blocks WHERE type IN ('promo','featured') AND active=1 AND draft=0 AND archived=0 AND retired=0"
    params=[]
    if exclude_id:query+=" AND id<>?";params.append(exclude_id)
    return list(db.execute(query,params))
def promotion_interval(item,now):
    start=instant(item["start_at"]) or now;end=instant(item["end_at"])
    return max(start,now).timestamp(),end.timestamp() if end else float("inf")
def promotion_snapshot(row,now):
    start=instant(row["start_at"]);end=instant(row["end_at"])
    age=max(0,(now-(start or datetime.fromisoformat(row["created_at"].replace("Z","+00:00")))).days) if status_of(row,now)=="Actif" else None
    return {"id":row["id"],"internal_name":row["internal_name"],"status":status_of(row,now),"start_at":row["start_at"],"end_at":row["end_at"],"active_days":age}
def concurrency(existing,start,end):
    if end<=start:return 0,[],[]
    overlap=[]
    for row in existing:
        rs,re=promotion_interval(row,datetime.now(timezone.utc))
        if rs<end and re>start:overlap.append((row,rs,re))
    points={start}
    for _,rs,re in overlap:
        if start<rs<end:points.add(rs)
        if start<re<end:points.add(re)
    ordered=sorted(points);maximum=1;segments=[]
    for index,point in enumerate(ordered):
        count=1+sum(1 for _,rs,re in overlap if rs<=point<re)
        maximum=max(maximum,count)
        if count>3:
            segment_end=ordered[index+1] if index+1<len(ordered) else end
            segments.append({"start_at":datetime.fromtimestamp(point,timezone.utc).isoformat().replace("+00:00","Z"),"end_at":None if segment_end==float("inf") else datetime.fromtimestamp(segment_end,timezone.utc).isoformat().replace("+00:00","Z"),"count":count})
    return maximum,overlap,segments
def promotion_check(item,exclude_id=None,db=None):
    if db is None:
        with connection() as conn:return promotion_check(item,exclude_id,conn)
    now=datetime.now(timezone.utc)
    rows=promotion_rows(db,exclude_id)
    all_rows=list(db.execute("SELECT * FROM content_blocks WHERE type IN ('promo','featured') AND archived=0 AND retired=0"))
    active=sum(status_of(row,now)=="Actif" for row in all_rows);programmed=sum(status_of(row,now)=="Programmé" for row in all_rows)
    if item["type"] not in {"promo","featured"} or not item["active"] or item["draft"]:
        return {"allowed":True,"maximum":0,"overlaps":[],"segments":[],"next_start":None,"active":active,"programmed":programmed}
    start,end=promotion_interval(item,now)
    maximum,overlap,segments=concurrency(rows,start,end)
    # Preserve the advisory contract; overlaps never prevent a save.
    return {"allowed":True,"maximum":maximum,"overlaps":[promotion_snapshot(row,now) for row,_,_ in overlap],"segments":segments,"next_start":None,"active":active,"programmed":programmed}

def button_data(data):
    icon=data.get("icon","website");icon="mail" if icon=="email" else icon;url=required(data,"url",2000)
    custom_icon=optional(data,"custom_icon",200)
    if custom_icon and not re.fullmatch(r"/uploads/[a-f0-9-]{36}\.(png|jpg|webp|gif)",custom_icon):raise ValueError("Icône personnelle invalide")
    if icon not in ICONS:raise ValueError("Icône invalide")
    if url.startswith("#"):
        if not re.fullmatch(r"#[A-Za-z][\w:-]*",url):raise ValueError("Ancre invalide")
    elif not valid_url(url):raise ValueError("URL invalide")
    return {"icon":icon,"custom_icon":custom_icon,"label":required(data,"label",100),"url":url,"active":1 if data.get("active",True) else 0}
def valid_metric(key,db=None):
    if key=="latest-video":return True
    table,prefix=("content_blocks","block:") if key.startswith("block:") else (("top_buttons","button:") if key.startswith("button:") else (None,None))
    if table:
        if db is not None:return db.execute(f"SELECT 1 FROM {table} WHERE id=?",(key.removeprefix(prefix),)).fetchone() is not None
        with connection() as db:return db.execute(f"SELECT 1 FROM {table} WHERE id=?",(key.removeprefix(prefix),)).fetchone() is not None
    return (key.startswith("social:") or key.startswith("link:")) and len(key)<=2048

def save_content(db,item,item_id=None):
    storage.require_file(UPLOADS,item.get("image"),db,DATA_DIR/"assets",STATIC/"assets")
    item=dict(item);timed=item.pop("calendar_timed",None)
    stamp=now_iso()
    if item_id:
        if not isinstance(item_id,str) or not db.execute("SELECT 1 FROM content_blocks WHERE id=?",(item_id,)).fetchone():raise ValueError("Bloc introuvable")
        values={**item,"updated_at":stamp}
        db.execute("UPDATE content_blocks SET "+",".join(k+"=?" for k in values)+" WHERE id=?",[*values.values(),item_id])
    else:
        item_id=str(uuid.uuid4())
        pos=db.execute("SELECT COALESCE(MAX(position),-1)+1 FROM content_blocks WHERE archived=0").fetchone()[0]
        values={**item,"id":item_id,"position":pos,"archived":0,"created_at":stamp,"updated_at":stamp}
        db.execute("INSERT INTO content_blocks ("+",".join(values)+") VALUES ("+",".join("?" for _ in values)+")",list(values.values()))
    if timed is not None:
        ids=set(json.loads(instance.get(db,"admin.calendar_timed") or "[]"))
        ids.intersection_update(r[0] for r in db.execute("SELECT id FROM content_blocks"))
        if timed:ids.add(item_id)
        else:ids.discard(item_id)
        instance.put(db,"admin.calendar_timed",json.dumps(sorted(ids)))
    return item_id

def save_content_request(db,data,ident=None):
    current=db.execute('SELECT * FROM content_blocks WHERE id=?',(ident,)).fetchone() if ident else None
    if ident and not current:raise ValueError('Bloc introuvable')
    if current:data={'type':current['type'],'internal_name':current['internal_name'],**data}
    result=None
    # A legacy GET/PUT roundtrip may echo the new read-only metadata. Only an
    # explicit affiliation operation enters the preview/confirmation protocol.
    explicit=('expected_url' in data or 'apply_partner' in data or data.get('detect') is True or
              ('partner_id' in data and (not current or data['partner_id']!=affiliate_partners.campaign_metadata(db,ident,current['url'])['partner_id'])))
    if data.get('type') in CAMPAIGN_TYPES and explicit:
        result=affiliate_partners.preview_campaign(db,data,ident,valid_url)
        affiliate_partners.check_campaign_preview(data,result)
    fields={**data,'url':result['url']} if result else data
    item=block_data(fields,allow_legacy_image=bool(current and current['image'] and current['image']==data.get('image')))
    saved=save_content(db,item,ident)
    if result:affiliate_partners.save_campaign_metadata(db,saved,result)
    elif current and (current['url']!=item['url'] or item['type'] not in CAMPAIGN_TYPES):
        db.execute('DELETE FROM campaign_partners WHERE campaign_id=?',(saved,))
    return saved

LEGACY_BACKUP_TABLES=('content_blocks','top_buttons','settings','counts','story_links','footer_quotes')
TRACKING_BACKUP_TABLES=('tracking_sources','tracked_links','tracked_tokens')
SHORT_BACKUP_TABLES=('short_aliases',)
SOURCE_BACKUP_TABLES=('tracking_source_keys',)
PARTNER_BACKUP_TABLES=('affiliate_partners','tracked_link_partners')
CAMPAIGN_PARTNER_BACKUP_TABLES=('campaign_partners',)
BACKUP_TABLES=LEGACY_BACKUP_TABLES+TRACKING_BACKUP_TABLES+SHORT_BACKUP_TABLES+SOURCE_BACKUP_TABLES+PARTNER_BACKUP_TABLES+CAMPAIGN_PARTNER_BACKUP_TABLES
BACKUP_LIMIT=64*1024*1024
UPLOAD_NAME=re.compile(r'[a-f0-9-]{36}\.(jpg|png|webp|gif)')

def restore_safety(db):
    """A coherent pre-restore SQLite backup plus every currently owned local file."""
    target=DATA_DIR/'restore-safety'/str(uuid.uuid4());target.mkdir(parents=True)
    with closing(sqlite3.connect(DB)) as source,closing(sqlite3.connect(target/'analytics.db')) as saved:
        source.backup(saved)
    for key in storage.references(db):
        origin=DATA_DIR/key if key.startswith('assets/') else UPLOADS/key
        if origin.is_file() and not origin.is_symlink():
            destination=target/key if key.startswith('assets/') else target/'uploads'/key
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(origin,destination)
    return target

def export_backup():
    with DATA_LOCK,connection() as db:
        tables={table:[dict(row) for row in db.execute('SELECT * FROM '+table)] for table in BACKUP_TABLES}
        for row in tables['tracked_links']:row.pop('category',None)
        references={r['image'] for r in tables['content_blocks']}
        references.update(r['custom_icon'] for r in tables['top_buttons'])
        references.update(r['value'] for r in tables['settings'] if r['key'] in {'profile.avatar','profile.logo','appearance.campaign_image'})
        references.update(themes.references(themes.state(db)['items'][1:]))
        images={};size=0
        for ref in references:
            if not ref.startswith('/uploads/'):continue
            name=ref.removeprefix('/uploads/')
            if not UPLOAD_NAME.fullmatch(name):raise ValueError('Référence image invalide')
            try:raw=(UPLOADS/name).read_bytes()
            except OSError as exc:raise ValueError('Une image référencée est introuvable : '+name) from exc
            size+=len(raw)
            if size>40*1024*1024:raise ValueError('Sauvegarde trop volumineuse : sauvegarder le volume serveur')
            images[name]=base64.b64encode(raw).decode('ascii')
        assets={}
        for path in (DATA_DIR/'assets').glob('*'):
            if path.is_file():assets[path.name]=base64.b64encode(path.read_bytes()).decode('ascii')
        result={'format':'links-backup','version':3,'created_at':now_iso(),'software_version':software_version(),'instance_id':instance.get(db,'app.instance_id'),'tables':tables,'images':images,'assets':assets,'affiliation':affiliation.export_backup(db),'descriptions':descriptions.export_backup(db)}
        encoded=json.dumps(result,ensure_ascii=False).encode()
        if len(encoded)>BACKUP_LIMIT:raise ValueError('Sauvegarde supérieure à 64 Mo : sauvegarder le volume serveur')
        return encoded

def restore_backup(data,preview=False):
    # Validation and merging must never mutate a caller's reusable backup object.
    data=copy.deepcopy(data)
    if data.get('format') not in {'links-backup','domotik-links-backup'} or data.get('version') not in {1,2,3}:raise ValueError('Ce fichier n’est pas une sauvegarde Links compatible')
    tables=data.get('tables');images=data.get('images')
    if not isinstance(tables,dict) or not isinstance(images,dict):raise ValueError('Sauvegarde incomplète')
    if data.get('version')<3:
        expected={'content_blocks','top_buttons','settings','counts'}
        if not expected<=set(tables) or set(tables)-set(BACKUP_TABLES):raise ValueError('Sauvegarde incomplète')
        with connection() as db:
            for table in {'footer_quotes','story_links'}-set(tables):tables[table]=[dict(r) for r in db.execute('SELECT * FROM '+table)]
            # Older formats did not know these event types. Preserve them once.
            existing={(r['day'],r['source'],r['kind'],r['link']) for r in tables['counts']}
            for r in db.execute("SELECT * FROM counts WHERE kind IN ('story','promo_code_copy')"):
                if (r['day'],r['source'],r['kind'],r['link']) not in existing:tables['counts'].append(dict(r))
    missing=set(TRACKING_BACKUP_TABLES)-set(tables)
    if missing:
        if missing!=set(TRACKING_BACKUP_TABLES):raise ValueError('Sauvegarde de liens suivis incomplète')
        with connection() as db:
            for table in TRACKING_BACKUP_TABLES:tables[table]=[dict(r) for r in db.execute('SELECT * FROM '+table)]
            old_keys={(r['day'],r['source'],r['kind'],r['link']) for r in tables['counts']}
            for row in db.execute("SELECT * FROM counts WHERE kind='tracked'"):
                if (row['day'],row['source'],row['kind'],row['link']) not in old_keys:tables['counts'].append(dict(row))
    if 'short_aliases' not in tables:
        with connection() as db:tables['short_aliases']=[dict(r) for r in db.execute('SELECT * FROM short_aliases')]
    if 'tracking_source_keys' not in tables:
        tables['tracking_source_keys']=[]
    missing_partners=set(PARTNER_BACKUP_TABLES)-set(tables)
    if missing_partners:
        if missing_partners!=set(PARTNER_BACKUP_TABLES):raise ValueError('Sauvegarde de partenaires incomplète')
        with connection() as db:
            for table in PARTNER_BACKUP_TABLES:tables[table]=[dict(row) for row in db.execute('SELECT * FROM '+table)]
    if 'campaign_partners' not in tables:
        with connection() as db:tables['campaign_partners']=[dict(row) for row in db.execute('SELECT * FROM campaign_partners')]
    if set(tables)!=set(BACKUP_TABLES):raise ValueError('Sauvegarde incomplète')
    assets=data.get('assets',{})
    if not isinstance(assets,dict):raise ValueError('Assets invalides')
    asset_bytes={}
    for name,encoded in assets.items():
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9._-]+\.(webp|jpg|jpeg|png|gif|svg)',name) or not isinstance(encoded,str):raise ValueError('Asset invalide')
        raw=base64.b64decode(encoded,validate=True)
        user_images.validate_legacy_asset(raw,Path(name).suffix)
        old=DATA_DIR/'assets'/name
        if old.exists() and old.read_bytes()!=raw:raise ValueError('Asset historique différent : restauration refusée pour conserver son URL')
        asset_bytes[name]=raw
    if sum(map(len,asset_bytes.values()))>40*1024*1024:raise ValueError('Assets trop volumineux')
    decoded={};mapping={};written=[];size=0
    for name,encoded in images.items():
        if not isinstance(name,str) or not UPLOAD_NAME.fullmatch(name) or not isinstance(encoded,str):raise ValueError('Nom ou format image invalide')
        try:raw=base64.b64decode(encoded,validate=True)
        except (ValueError,binascii.Error) as exc:raise ValueError('Image corrompue') from exc
        size+=len(raw)
        if not 0<len(raw)<=4*1024*1024 or size>40*1024*1024:raise ValueError('Images trop volumineuses')
        user_images.validate(raw,Path(name).suffix)
        new_name=str(uuid.uuid4())+Path(name).suffix
        mapping['/uploads/'+name]='/uploads/'+new_name;decoded[new_name]=raw
    try:
        with DATA_LOCK,connection() as db:
            db.execute('BEGIN IMMEDIATE')
            retained_rows=set()
            incoming_instance=data.get('instance_id')
            if incoming_instance and incoming_instance!=instance.get(db,'app.instance_id'):
                if db.execute('SELECT 1 FROM counts LIMIT 1').fetchone() or db.execute('SELECT 1 FROM story_links LIMIT 1').fetchone() or db.execute('SELECT 1 FROM tracked_tokens LIMIT 1').fetchone():
                    raise ValueError('Sauvegarde d’une autre instance : fusion des historiques refusée. Utiliser une installation vide pour le transfert.')
            legacy_link_categories=None
            for table in BACKUP_TABLES:
                rows=tables[table]
                if not isinstance(rows,list) or len(rows)>500000:raise ValueError('Table invalide : '+table)
                schema=list(db.execute('PRAGMA table_info('+table+')'))
                if table=='tracked_links':
                    if any(column['name']=='category' for column in schema):
                        legacy_link_categories={row['id']:row['category'] for row in db.execute('SELECT id,category FROM tracked_links')}
                    schema=[column for column in schema if column['name']!='category']
                columns=[c['name'] for c in schema]
                primary=[c['name'] for c in schema if c['pk']]
                keys=[tuple(row.get(k) for k in primary) for row in rows if isinstance(row,dict)]
                if len(keys)!=len(set(keys)):raise ValueError('Identifiants en double : '+table)
                for row in rows:
                    if table=='tracked_links' and isinstance(row,dict):row.pop('category',None)
                    if table=='tracked_link_partners' and isinstance(row,dict):row.setdefault('original_url','')
                    if table=='content_blocks' and isinstance(row,dict) and 'promo_code' not in row:row['promo_code']=''
                    if table=='top_buttons' and isinstance(row,dict) and 'custom_icon' not in row:row['custom_icon']=''
                    if table in {'content_blocks','top_buttons'} and isinstance(row,dict):row.setdefault('retired',0)
                    if not isinstance(row,dict) or set(row)!=set(columns):raise ValueError('Structure incompatible : '+table)
                    for column in schema:
                        value=row[column['name']]
                        if value is None:
                            if column['notnull'] or column['pk']:raise ValueError('Valeur obligatoire absente')
                        elif column['type']=='INTEGER':
                            if type(value) is not int or not 0<=value<2**53:raise ValueError('Compteur ou position invalide')
                        elif not isinstance(value,str) or len(value)>16384:raise ValueError('Texte invalide')
                    if table=='affiliate_partners':
                        if not re.fullmatch(r'[a-f0-9]{32}',row['id']):raise ValueError('Identifiant de partenaire invalide')
                        if (row['id']==uuid.uuid5(uuid.NAMESPACE_URL,'links:affiliate-partner:sanyipace').hex
                                and not any(setting['key']==affiliate_partners.SANYIPACE_MIGRATION for setting in tables['settings'])):
                            row['domains']=json.dumps(affiliate_partners.corrected_sanyipace_domains(json.loads(row['domains'])))
                        affiliate_partners.partner_input({**row,'domains':json.loads(row['domains'])})
                    elif table=='tracked_link_partners':
                        if any(not re.fullmatch(r'[a-f0-9]{32}',row[key]) for key in ('link_id','partner_id')):raise ValueError('Association de partenaire invalide')
                        if row['original_url'] and (len(row['original_url'])>2000 or not affiliate_partners.http_url(row['original_url'])):raise ValueError('URL d’origine invalide')
                    elif table=='campaign_partners':
                        if not row['campaign_id'] or (row['partner_id'] is not None and not re.fullmatch(r'[a-f0-9]{32}',row['partner_id'])):raise ValueError('Association de campagne invalide')
                        if not valid_url(row['original_url']) or not valid_url(row['final_url']):raise ValueError('URL de campagne invalide')
                        if row['partner_id'] is not None and not affiliate_partners.http_url(row['original_url']):raise ValueError('URL affiliée invalide')
                    elif table=='content_blocks':
                        block_data(row,allow_legacy_image=True)
                        if any(row[k] not in (0,1) for k in ['active','draft','archived','retired']):raise ValueError('État invalide')
                    elif table=='top_buttons':
                        button_data({**row,'icon':'mail' if row['icon']=='email' else row['icon']})
                        if row['retired'] not in (0,1):raise ValueError('État invalide')
                    elif table=='counts':
                        date.fromisoformat(row['day'])
                        if row['kind'] not in {'view','click','impression','story','tracked','promo_code_copy'} or row['total']<1:raise ValueError('Statistique invalide')
                        if row['kind']=='promo_code_copy':
                            snapshot=json.loads(row['link'])
                            if not isinstance(snapshot,dict) or set(snapshot)!={'id','name','code','timestamp'} or any(not isinstance(v,str) for v in snapshot.values()) or not snapshot['code'] or len(snapshot['code'])>80:raise ValueError('Copie de code invalide')
                            instant(snapshot['timestamp'])
                        if row['kind']=='tracked' and (not re.fullmatch(r'tracked:tk_[A-Za-z0-9_-]{16}:\d{2}',row['link']) or int(row['link'][-2:])>23 or not re.fullmatch(r'tracked:[a-f0-9]{32}',row['source'])):raise ValueError('Statistique de lien suivi invalide')
                        if row['kind']=='story' and ((row['source'] not in {'instagram-story','shared-unknown','instagram','youtube','facebook','tiktok','discord','newsletter','site','mail','qr'} and not re.fullmatch(r'tracked:[a-f0-9]{32}',row['source'])) or not re.fullmatch(r'story:st_[A-Za-z0-9_-]{16}:\d{2}',row['link']) or int(row['link'][-2:])>23):raise ValueError('Statistique Story invalide')
                    elif table=='story_links':
                        if not STORY_TOKEN.fullmatch(row['token']) or row['deleted'] not in (0,1) or not row['name'] or not row['promotion_id']:raise ValueError('Lien Story invalide')
                        instant(row['created_at'])
                    elif table=='tracking_sources':
                        if not tracked_links.IDENT.fullmatch(row['id']) or not row['name'].strip() or len(row['name'])>100 or row['active'] not in (0,1):raise ValueError('Source suivie invalide')
                    elif table=='tracking_source_keys':
                        if row['key'] not in tracked_links.SOURCE_KEYS or row['source_id'] is not None and not tracked_links.IDENT.fullmatch(row['source_id']):raise ValueError('Identité de source invalide')
                    elif table=='tracked_links':
                        if not tracked_links.IDENT.fullmatch(row['id']) or not row['name'].strip() or len(row['name'])>160 or not story_url_valid(row['url']) or row['archived'] not in (0,1) or row['enabled'] not in (0,1):raise ValueError('Lien suivi invalide')
                    elif table=='tracked_tokens':
                        if not tracked_links.TOKEN.fullmatch(row['token']) or not tracked_links.IDENT.fullmatch(row['link_id']) or not tracked_links.IDENT.fullmatch(row['source_id']):raise ValueError('Jeton suivi invalide')
                    elif table=='short_aliases':
                        if (not short_urls.CODE.fullmatch(row['code']) or not short_urls.LONG_TOKEN.fullmatch(row['target_token']) or
                            row['revoked'] not in (0,1) or not (
                                row['source'] in short_urls.CAMPAIGN_SOURCES or
                                re.fullmatch(r'tracked:[a-f0-9]{32}',row['source']))):raise ValueError('Lien court invalide')
                        instant(row['created_at'])
                    elif table=='footer_quotes':
                        if not row['text'].strip() or len(row['text'])>1000 or row['active'] not in (0,1):raise ValueError('Citation invalide')
                        instant(row['created_at'])
                    elif row['key'] not in instance.CONFIG_KEYS:raise ValueError('Réglage inconnu')
            if len(tables["footer_quotes"])>300:raise ValueError("Maximum 300 citations")
            incoming_settings={r["key"]:r["value"] for r in tables["settings"]}
            theme_rows=themes.validate_backup(incoming_settings)
            validate_settings(incoming_settings)
            for row in tables["settings"]:
                if row["key"]=="app.version":checked_version(row["value"])
            setting_keys={row["key"] for row in tables["settings"]}
            for row in db.execute("SELECT * FROM settings"):
                if row["key"] in {"auth.mode","app.setup_completed","app.config_schema_version"}:
                    tables["settings"]=[r for r in tables["settings"] if r["key"]!=row["key"]];tables["settings"].append(dict(row));continue
                if row['key']=='analytics.metric_aliases':
                    aliases={**json.loads(incoming_settings.get(row['key'],'{}')),**json.loads(row['value'])}
                    for incoming_row in tables['settings']:
                        if incoming_row['key']==row['key']:incoming_row['value']=json.dumps(aliases,ensure_ascii=False)
                if row['key']=='analytics.source_rules':
                    rules={r['key']:r for r in json.loads(incoming_settings.get(row['key'],'[]'))}
                    rules.update({r['key']:r for r in json.loads(row['value'])})
                    merged=instance.source_rules(list(rules.values()))
                    for incoming_row in tables['settings']:
                        if incoming_row['key']==row['key']:incoming_row['value']=merged
                if row["key"] not in setting_keys:tables["settings"].append(dict(row))
            # Preserve every content identity, including objects published after backup.
            published={r[0] for r in db.execute('SELECT promotion_id FROM story_links')}
            for table,media in [('content_blocks','image'),('top_buttons','custom_icon')]:
                incoming_rows={r['id']:r for r in tables[table]}
                for old in db.execute('SELECT * FROM '+table):
                    row=incoming_rows.get(old['id'])
                    if row is None:
                        row=dict(old)
                        if table=='content_blocks':row['archived']=1
                        else:row['active']=0;row['retired']=1
                        tables[table].append(row)
                        retained_rows.add((table,row['id']))
                    else:
                        row['retired']=max(row['retired'],old['retired'])
                        if row['retired']:
                            if table=='content_blocks':row['archived']=1
                            else:row['active']=0
                        if table=='content_blocks' and old['id'] in published:
                            row['url']=old['url']
            # Codes are never reassigned, even when restoring a different backup.
            incoming={r['token']:r for r in tables['story_links']}
            for old in db.execute('SELECT * FROM story_links'):
                if old['token'] in incoming:
                    if incoming[old['token']]['promotion_id']!=old['promotion_id']:raise ValueError('Un identifiant Story ne peut pas changer de promotion')
                    incoming[old['token']]['deleted']=max(incoming[old['token']]['deleted'],old['deleted'])
                elif any(r['promotion_id']==old['promotion_id'] for r in incoming.values()):raise ValueError('Identifiants Story incompatibles avec les liens existants')
                else:tables['story_links'].append(dict(old))
            # Preserve all previously published tracked tokens through restores.
            existing_links={r['id']:r for r in tables['tracked_links']}
            existing_sources={r['id']:r for r in tables['tracking_sources']}
            # A restore must not discard currently configured private links
            # or source lifetime counters that were added after the backup.
            for old in db.execute('SELECT * FROM tracked_links'):
                if old['id'] not in existing_links:
                    row=dict(old);tables['tracked_links'].append(row);existing_links[old['id']]=row
                else:
                    # A backup must not silently roll back a published destination or suspension.
                    for key in ('url','enabled','archived'):existing_links[old['id']][key]=old[key]
            for old in db.execute('SELECT * FROM tracking_sources'):
                if old['id'] not in existing_sources:
                    row=dict(old)
                    taken={source['name'].casefold() for source in existing_sources.values()}
                    if row['name'].casefold() in taken:
                        # Independent source IDs remain distinct, even with the same label.
                        original=row['name'][:76]
                        row['name']=original+' (historique '+row['id'][:8]+')'
                        if row['name'].casefold() in taken:raise ValueError('Collision de sources de publication')
                    tables['tracking_sources'].append(row);existing_sources[old['id']]=row
                else:
                    row=existing_sources[old['id']]
                    row['story_click_total']=max(row['story_click_total'],old['story_click_total'])
            incoming_tokens={r['token']:r for r in tables['tracked_tokens']}
            existing_pairs={(r['link_id'],r['source_id']):r['token'] for r in incoming_tokens.values()}
            for old in db.execute('SELECT * FROM tracked_tokens'):
                if old['token'] in incoming_tokens:
                    row=incoming_tokens[old['token']]
                    if row['link_id']!=old['link_id'] or row['source_id']!=old['source_id']:raise ValueError('Un lien suivi ne peut pas être réattribué')
                    row['click_total']=max(row['click_total'],old['click_total'])
                else:
                    key=(old['link_id'],old['source_id'])
                    if key in existing_pairs:raise ValueError('Jetons suivis incompatibles')
                    incoming_tokens[old['token']]=dict(old)
                    tables['tracked_tokens'].append(dict(old))
                if old['link_id'] not in existing_links:
                    row=dict(db.execute('SELECT * FROM tracked_links WHERE id=?',(old['link_id'],)).fetchone())
                    tables['tracked_links'].append(row);existing_links[old['link_id']]=row
                if old['source_id'] not in existing_sources:
                    row=dict(db.execute('SELECT * FROM tracking_sources WHERE id=?',(old['source_id'],)).fetchone())
                    tables['tracking_sources'].append(row);existing_sources[old['source_id']]=row
            old_keys={(r['day'],r['source'],r['kind'],r['link']) for r in tables['counts']}
            for old in db.execute("SELECT * FROM counts WHERE kind='tracked'"):
                if (old['day'],old['source'],old['kind'],old['link']) not in old_keys:tables['counts'].append(dict(old))
            tracked_tokens={r['token'] for r in tables['tracked_tokens']}
            if any(r['kind']=='tracked' and r['link'].split(':')[1] not in tracked_tokens for r in tables['counts']):raise ValueError('Lien suivi manquant')
            affiliate_partners.merge_backup(db,tables)
            affiliate_partners.merge_campaign_backup(db,tables)
            # Short codes are never recycled or reassigned after restore.
            aliases={r['code']:r for r in tables['short_aliases']}
            for old in db.execute('SELECT * FROM short_aliases'):
                if old['code'] in aliases:
                    entry=aliases[old['code']]
                    if (entry['target_token'],entry['source'])!=(old['target_token'],old['source']):
                        raise ValueError('Un lien court ne peut pas changer de cible ou de source')
                    entry['revoked']=max(entry['revoked'],old['revoked'])
                else:
                    entry=dict(old);tables['short_aliases'].append(entry);aliases[old['code']]=entry
            source_keys={r['key']:r for r in tables['tracking_source_keys']}
            for old in db.execute('SELECT * FROM tracking_source_keys'):
                if old['key'] in source_keys:
                    if source_keys[old['key']]['source_id']!=old['source_id'] and old['source_id'] is not None:
                        used=db.execute('SELECT 1 FROM short_aliases WHERE source IN (?,?) LIMIT 1',(old['key'],'tracked:'+old['source_id'])).fetchone()
                        clicks=db.execute('SELECT story_click_total FROM tracking_sources WHERE id=?',(old['source_id'],)).fetchone()
                        if used or clicks and clicks[0]:raise ValueError('Une source historique ne peut pas être réattribuée')
                elif old['source_id'] is None or old['source_id'] in existing_sources:
                    tables['tracking_source_keys'].append(dict(old))
            if any(r['source_id'] is not None and r['source_id'] not in existing_sources for r in tables['tracking_source_keys']):raise ValueError('Source historique manquante')
            # Aggregate snapshots overlap: keep maxima, never add them a second time.
            indexed={(r['day'],r['source'],r['kind'],r['link']):r for r in tables['counts']}
            for old in db.execute("SELECT * FROM counts"):
                key=(old['day'],old['source'],old['kind'],old['link'])
                if key in indexed:indexed[key]['total']=max(indexed[key]['total'],old['total'])
                else:
                    entry=dict(old);tables['counts'].append(entry);indexed[key]=entry
            tokens={r['token'] for r in tables['story_links']}
            if any(r['kind']=='story' and r['link'].split(':')[1] not in tokens for r in tables['counts']):raise ValueError('Référent Story manquant')
            # Every uploaded image used by the restored content must exist in this backup.
            for row in tables['content_blocks']:
                if row['image'].startswith('/uploads/'):
                    if ('content_blocks',row['id']) in retained_rows:
                        storage.require_file(UPLOADS,row['image'],db);continue
                    if row['image'] not in mapping:raise ValueError('Image manquante dans la sauvegarde')
                    row['image']=mapping[row['image']]
            for row in tables['top_buttons']:
                if row['custom_icon']:
                    if ('top_buttons',row['id']) in retained_rows:
                        storage.require_file(UPLOADS,row['custom_icon'],db);continue
                    if row['custom_icon'] not in mapping:raise ValueError('Icône personnelle manquante')
                    row['custom_icon']=mapping[row['custom_icon']]
            for row in tables['settings']:
                if row['key'] in {'profile.avatar','profile.logo','appearance.campaign_image'} and row['value'].startswith('/uploads/'):
                    if row['key']=='appearance.campaign_image' and row['key'] not in setting_keys:
                        storage.require_file(UPLOADS,row['value'],db);continue
                    if row['value'] not in mapping:raise ValueError('Image de profil manquante')
                    row['value']=mapping[row['value']]
            for theme in theme_rows:
                for key,ref in theme['tokens'].items():
                    if isinstance(ref,str) and ref.startswith('/uploads/'):
                        if ref not in mapping:raise ValueError('Image de thème manquante')
                        theme['tokens'][key]=mapping[ref]
            for row in tables['settings']:
                if row['key']=='appearance.themes':row['value']=json.dumps(theme_rows)
            refs=[r['image'] for r in tables['content_blocks']]+[r['value'] for r in tables['settings'] if r['key'] in {'profile.logo','profile.avatar','appearance.campaign_image'}]
            for ref in refs:
                if ref.startswith('/assets/') and not (STATIC/ref[1:]).is_file() and not (DATA_DIR/ref[1:]).is_file() and ref[8:] not in asset_bytes:raise ValueError('Asset référencé manquant')
            description_restore=descriptions.restore_backup(db,data.get('descriptions'))
            affiliation_restore=affiliation.restore_backup(db,data.get('affiliation'))
            summary={'descriptions':description_restore,'affiliation':affiliation_restore,'blocks':len(tables['content_blocks']),'buttons':len(tables['top_buttons']),'images':len(images),
                     'retained_content':len(retained_rows),'published_redirects':len(tables['story_links'])+len(tables['tracked_tokens']),
                     'counter_total':sum(row['total'] for row in tables['counts'])}
            canonical={r['token'] for r in tables['story_links']}|{r['token'] for r in tables['tracked_tokens']}
            if any(not r['revoked'] and r['target_token'] not in canonical for r in tables['short_aliases']):raise ValueError('Cible de lien court manquante')
            if preview:
                db.rollback()
                return summary
            # Backup the current SQLite state only after validation, before replacing rows.
            restore_safety(db)
            db.execute('DELETE FROM campaign_partners')
            for table in reversed(PARTNER_BACKUP_TABLES):
                db.execute('DELETE FROM '+table)
            for table in SOURCE_BACKUP_TABLES+SHORT_BACKUP_TABLES:
                db.execute('DELETE FROM '+table)
            for table in reversed(TRACKING_BACKUP_TABLES):
                db.execute('DELETE FROM '+table)
            for table in LEGACY_BACKUP_TABLES:
                db.execute('DELETE FROM '+table)
                columns=[c['name'] for c in db.execute('PRAGMA table_info('+table+')')]
                db.executemany('INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',[[row[c] for c in columns] for row in tables[table]])
            for table in TRACKING_BACKUP_TABLES+SHORT_BACKUP_TABLES+SOURCE_BACKUP_TABLES+PARTNER_BACKUP_TABLES+CAMPAIGN_PARTNER_BACKUP_TABLES:
                columns=[c['name'] for c in db.execute('PRAGMA table_info('+table+')')]
                if table=='tracked_links' and legacy_link_categories is not None:
                    # Storage compatibility only: never import an obsolete category.
                    for row in tables[table]:row['category']=legacy_link_categories.get(row['id'],'')
                db.executemany('INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',[[row[c] for c in columns] for row in tables[table]])
            db.execute("INSERT OR REPLACE INTO settings VALUES('content.initialized','1')")
            # New filenames ensure that a failed restore cannot overwrite current images.
            for name,raw in decoded.items():
                target=UPLOADS/name;written.append(target);storage.write(target,raw)
            (DATA_DIR/'assets').mkdir(exist_ok=True)
            for name,raw in asset_bytes.items():
                target=DATA_DIR/'assets'/name
                if not target.exists():written.append(target);storage.write(target,raw)
            init_version(db)
            storage.scan(db,UPLOADS,assets=DATA_DIR/'assets',system_assets=STATIC/'assets')
            db.execute('DELETE FROM admin_sessions')
        with connection() as db:sync_configuration(db)
        return summary
    except Exception:
        for path in written:path.unlink(missing_ok=True)
        raise


def validate_settings(values):
    if 'app.instance_id' in values and not re.fullmatch(r'[a-f0-9]{32}',values['app.instance_id']):raise ValueError('Identité d’instance invalide')
    if 'admin.calendar_timed' in values:
        ids=json.loads(values['admin.calendar_timed'])
        if not isinstance(ids,list) or any(not isinstance(x,str) or not re.fullmatch(r'[a-f0-9-]{36}',x) for x in ids):raise ValueError('Modes horaires invalides')
    for order_key in ['admin.content_order','public.section_order']:
        if order_key not in values:continue
        order=json.loads(values[order_key])
        if not isinstance(order,list) or len(order)!=3 or any(not isinstance(x,str) for x in order) or set(order)!={'classic','video','highlight'}:raise ValueError('Ordre des sections invalide')
    if 'site.url' in values:values['site.url']=instance.site_url(values['site.url'],allow_empty=True)
    if 'app.timezone' in values:instance.timezone_name(values['app.timezone'])
    if 'appearance.campaign_image' in values:campaign_image_value(values['appearance.campaign_image'])
    if 'analytics.source_rules' in values:instance.source_rules(values['analytics.source_rules'])
    for key in ['analytics.enabled','video.enabled','app.setup_completed']:
        if key in values and values[key] not in {'true','false'}:raise ValueError('Valeur booléenne invalide')
    if 'auth.mode' in values and values['auth.mode'] not in {'external','local'}:raise ValueError('Mode d’accès invalide')
    if 'analytics.metric_aliases' in values:
        aliases=json.loads(values['analytics.metric_aliases'])
        if not isinstance(aliases,dict) or any(not isinstance(k,str) or not isinstance(v,str) or not v.startswith(('block:','button:')) for k,v in aliases.items()):raise ValueError('Correspondances statistiques invalides')

def configuration_input(data):
    if data and set(data)<= {'content_order','video_enabled'}:
        values={}
        if 'content_order' in data:values['admin.content_order']=json.dumps(data['content_order'])
        if 'video_enabled' in data:
            if type(data['video_enabled']) is not bool:raise ValueError('Choix invalide')
            values['video.enabled']='true' if data['video_enabled'] else 'false'
        validate_settings(values)
        return values
    values={'profile.name':required(data,'name',120),'profile.tagline':optional(data,'tagline',200),'profile.description':optional(data,'description',300)}
    for key,limit in [('avatar',2048),('logo',2048),('footer_owner',120),('site_url',2048),('timezone',100),('video_channel_id',100)]:
        if key in data:values[{'avatar':'profile.avatar','logo':'profile.logo','footer_owner':'footer.owner','site_url':'site.url','timezone':'app.timezone','video_channel_id':'video.channel_id'}[key]]=optional(data,key,limit)
    for key,target in [('analytics_enabled','analytics.enabled'),('video_enabled','video.enabled')]:
        if key in data:
            if type(data[key]) is not bool:raise ValueError('Choix invalide')
            values[target]='true' if data[key] else 'false'
    if 'source_rules' in data:values['analytics.source_rules']=instance.source_rules(data['source_rules'])
    for key in ['profile.logo','profile.avatar']:
        if key in values and values[key] and not (re.fullmatch(r'/uploads/[a-f0-9-]{36}\.(jpg|png|webp|gif)',values[key]) or re.fullmatch(r'/assets/[A-Za-z0-9._-]+',values[key])):raise ValueError('Importer une image locale pour le profil')
        if key in values and values[key] and not (UPLOADS/values[key][9:]).is_file() and not (DATA_DIR/values[key][1:]).is_file() and not (STATIC/values[key][1:]).is_file():raise ValueError('Image de profil introuvable')
    if 'video.channel_id' in values and values['video.channel_id'] and not re.fullmatch(r'UC[\w-]{22}',values['video.channel_id']):raise ValueError('Identifiant YouTube invalide')
    validate_settings(values)
    return values

def youtube_status():
    with connection() as db:channel=instance.get(db,'video.channel_id');enabled=instance.get(db,'video.enabled')=='true'
    key=youtube.read_key(DATA_DIR);legacy=bool(os.environ.get('CREATOR_STUDIO_URL') and os.environ.get('CREATOR_STUDIO_API_KEY'))
    return {'channel':channel,'enabled':enabled,'key_configured':bool(key),'key_managed':bool(os.environ.get('YOUTUBE_API_KEY')),'configured':bool(channel and key) or legacy,'legacy':legacy and not bool(channel and key)}
def youtube_test(data):
    status=youtube_status();channel=data.get('channel',status['channel']);key=data.get('api_key') or youtube.read_key(DATA_DIR)
    if not channel or (not key and status['legacy']):
        if not status['legacy']:raise ValueError('Renseignez votre chaîne YouTube.')
        try:
            with urlopen('http://127.0.0.1:3002/latest-video.json',timeout=9) as response:video=json.load(response)
            return {'video':video,'legacy':True}
        except (OSError,ValueError):raise ValueError('La source serveur actuelle est indisponible.') from None
    return youtube.latest(channel,key,force=True)
def save_youtube(data):
    channel=data.get('channel','')
    if not isinstance(channel,str) or type(data.get('enabled')) is not bool:raise ValueError('Configuration YouTube invalide.')
    channel=channel.strip()
    if channel:youtube.channel_query(channel)
    if data.get('api_key') and (not isinstance(data['api_key'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{20,200}',data['api_key'])):raise ValueError('Clé API invalide.')
    key=data.get('api_key') or youtube.read_key(DATA_DIR)
    # Resolve handles before persistence; retain the private existing source if no API key is available.
    if channel and key and not data.get('remove_key') and (data.get('api_key') or channel!=youtube_status()['channel']):channel=youtube.latest(channel,key,force=True)['channel_id']
    elif channel and not re.fullmatch(r'UC[\w-]{22}',channel):raise ValueError('Ajoutez une clé API pour résoudre cette chaîne.')
    if data.get('remove_key') is True:youtube.store_key(DATA_DIR,'')
    elif data.get('api_key'):youtube.store_key(DATA_DIR,data['api_key'])
    with connection() as db:
        instance.put(db,'video.channel_id',channel);instance.put(db,'video.enabled','true' if data['enabled'] else 'false')
    return youtube_status()
def latest_video():
    status=youtube_status()
    if not status['enabled']:return None
    if status['channel'] and status['key_configured']:return youtube.latest(status['channel'],youtube.read_key(DATA_DIR))['video']
    if status['legacy']:
        with urlopen('http://127.0.0.1:3002/latest-video.json',timeout=9) as response:return json.load(response)
    raise ValueError('Source vidéo non configurée.')

def public_mutation(path):
    return (path.startswith(('/api/content','/api/buttons','/api/settings','/api/restore','/api/setup','/api/promotions/replace'))
            and path not in {'/api/setup/check','/api/restore/preview','/api/content/preview'}
            or path=='/api/youtube' or (path.startswith('/api/quotes') and path!='/api/quotes/analyze')
            or (path.startswith('/api/appearance') and path not in {'/api/appearance/css','/api/appearance/css-export','/api/appearance/export'}))



# PulSe uses a narrow machine-to-machine API. Its token is never a LinKs admin
# session and grants no access to content editing, settings, or backups.
def pulse_token_ready():
    value=os.environ.get("PULSE_BRIDGE_TOKEN","")
    return 32<=len(value)<=512

def pulse_services():
    return SimpleNamespace(connection=connection,story_url_valid=story_url_valid,now_iso=now_iso,ORIGIN=ORIGIN)

def pulse_authenticated(header):
    if not pulse_token_ready():return False
    if not isinstance(header,str) or not header.startswith("Bearer "):return False
    token=header[7:]
    return secrets.compare_digest(os.environ["PULSE_BRIDGE_TOKEN"],token)

def pulse_links():
    with connection() as db:
        return {"links":[{"id":r["id"],"name":r["name"],"url":r["url"],
                          "enabled":bool(r["enabled"]),
                          "archived":bool(r["archived"])}
                         for r in db.execute("""SELECT id,name,url,enabled,archived
                           FROM tracked_links WHERE archived=0 AND enabled=1
                           ORDER BY created_at DESC LIMIT 400""")]}

def pulse_stats(period=7):
    if str(period) not in {"7","30"}:
        raise ValueError("Période PulSe invalide : 7 ou 30 jours requis")
    period=int(period)
    today=datetime.now(PARIS).date()
    first=today-timedelta(days=period-1)
    with connection() as db:
        daily={r["day"]:int(r["total"]) for r in db.execute(
            """SELECT day,COALESCE(SUM(total),0) AS total FROM counts
               WHERE day BETWEEN ? AND ? AND kind IN ('click','story','tracked')
               GROUP BY day""",(first.isoformat(),today.isoformat()))}
        story_clicks=db.execute("""SELECT COALESCE(SUM(total),0) FROM counts
               WHERE day BETWEEN ? AND ? AND kind='story'""",
               (first.isoformat(),today.isoformat())).fetchone()[0]
        instagram_ids=tracked_links.platform_source_ids(db,'instagram')
        independent_story_clicks=db.execute("""SELECT COALESCE(SUM(c.total),0)
               FROM counts c JOIN tracked_tokens t ON substr(c.link,9,length(t.token))=t.token
               JOIN tracking_sources s ON t.source_id=s.id
               WHERE c.day BETWEEN ? AND ? AND c.kind='tracked'
                 AND s.id IN ("""+','.join('?' for _ in instagram_ids or [''])+")",
               (first.isoformat(),today.isoformat(),*(instagram_ids or ['']))).fetchone()[0]
    days=[{"date":(first+timedelta(days=i)).isoformat(),
           "clicks":daily.get((first+timedelta(days=i)).isoformat(),0)} for i in range(period)]
    return {"today":days[-1]["clicks"],"last7":sum(d["clicks"] for d in days[-7:]),
            "period":period,"total":sum(d["clicks"] for d in days),
            "stories":int(story_clicks)+int(independent_story_clicks),
            "days":days}

def pulse_today(at=None):
    """One read snapshot of existing daily counters; no hourly inference or writes."""
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError('Date avec fuseau requise')
    zone = ZoneInfo('Europe/Paris')
    day = at.astimezone(zone).date()
    yesterday = day - timedelta(days=1)
    with connection() as db:
        db.execute('BEGIN')
        # Daily buckets cannot be converted to another timezone after collection.
        if instance.get(db, 'app.timezone', 'UTC') != 'Europe/Paris':
            return {'version': 1, 'available': False, 'reason': 'timezone'}
        totals = {r['day']: int(r['total']) for r in db.execute(
            """SELECT day,SUM(total) total FROM counts WHERE day BETWEEN ? AND ?
               AND kind IN ('click','story','tracked') GROUP BY day""",
            (yesterday.isoformat(), day.isoformat()))}
        rows = tracked_links.list_links(db, day.isoformat(), day.isoformat())
        sources = tracked_links.source_rows(db)
        enabled = instance.get(db, 'analytics.enabled', 'true') == 'true'
    source_totals = {}
    for row in rows:
        for source in row['sources']:
            source_totals[source['id']] = source_totals.get(source['id'], 0) + source['period']
    ranked = sorted((r for r in rows if r['period_clicks'] > 0), key=lambda r: (-r['period_clicks'], r['id']))[:5]
    ranked_sources = sorted((r for r in sources if source_totals.get(r['id'], 0) > 0), key=lambda r: (-source_totals[r['id']], r['id']))[:5]
    return {'version': 1, 'available': True, 'timezone': 'Europe/Paris',
            'generated_at': at.astimezone(timezone.utc).isoformat(),
            'scope': 'all-clicks', 'comparison': 'yesterday-full-day', 'analytics_enabled': enabled,
            'date': day.isoformat(), 'yesterday_date': yesterday.isoformat(),
            'today': totals.get(day.isoformat(), 0), 'yesterday': totals.get(yesterday.isoformat(), 0),
            'ranking_scope': 'tracked-links', 'tracked_total': sum(r['period_clicks'] for r in rows),
            'top_links': [{'id': r['id'], 'name': r['name'], 'clicks': r['period_clicks'],
                           'available': bool(r['enabled'] and not r['archived'])} for r in ranked],
            'sources': [{'id': r['id'], 'name': r['name'], 'platform': r['platform'],
                         'clicks': source_totals[r['id']]} for r in ranked_sources]}


def pulse_insights(period=7):
    # Read-only mobile projection of the existing tracked-link reporting engine.
    window=pulse_stats(period)
    with connection() as db:
        rows=tracked_links.list_links(db,window['days'][0]['date'],window['days'][-1]['date'])
        sources=tracked_links.source_rows(db)
    totals={}
    for row in rows:
        for source in row['sources']:
            totals[source['id']]=totals.get(source['id'],0)+source['period']
    ranked=sorted((row for row in rows if row['period_clicks']>0),key=lambda row:(-row['period_clicks'],row['id']))[:5]
    ranked_sources=sorted((row for row in sources if totals.get(row['id'],0)>0),key=lambda row:(-totals[row['id']],row['id']))[:5]
    return {'version':1,'period':window['period'],'scope':'tracked-links',
            'tracked_total':sum(row['period_clicks'] for row in rows),
            'active_campaigns':len(campaign_selection()['eligible_ids']),
            'top_links':[{'id':row['id'],'name':row['name'],'clicks':row['period_clicks'],
                          'available':bool(row['enabled'] and not row['archived'])} for row in ranked],
            'sources':[{'id':row['id'],'name':row['name'],'platform':row['platform'],
                        'clicks':totals[row['id']]} for row in ranked_sources]}


def pulse_youtube_story_link(video_id):
    # Freeze a video's destination in an existing private tracked link. Never
    # point an old Story at the dynamic "latest video" URL or accept a client URL.
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}",video_id):
        raise ValueError("Identifiant vidéo invalide")
    video=latest_video()
    if not isinstance(video,dict):raise ValueError("Aucune vidéo YouTube disponible")
    parsed=urlsplit(video.get("url", ""))
    current_id=(parsed.path[1:] if parsed.hostname=="youtu.be" else
                parse_qs(parsed.query).get("v",[""])[0] if parsed.hostname in {"youtube.com","www.youtube.com"} and parsed.path=="/watch" else "")
    if parsed.scheme!="https" or parsed.username or parsed.password or current_id!=video_id:
        raise ValueError("La dernière vidéo a changé : actualisez PulSe")
    destination="https://www.youtube.com/watch?v="+video_id
    ident=uuid.uuid5(uuid.NAMESPACE_URL,"pulse-youtube:"+video_id).hex
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        source=tracked_links.publication_source(db,ident)
        existing=db.execute("SELECT url FROM tracked_links WHERE id=?",(ident,)).fetchone()
        if existing and existing["url"]!=destination:
            raise ValueError("La destination vidéo a été modifiée dans LinKs")
        if not existing:
            title=video.get("title")
            title=title.strip()[:160] if isinstance(title,str) and title.strip() else "Vidéo YouTube"
            db.execute("INSERT INTO tracked_links(id,name,url,notes,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                       (ident,title,destination,"Créé depuis PulSe pour une vidéo précise",now_iso(),now_iso()))
        return tracked_links.token_link(db,ident,source["id"],ORIGIN,now_iso())


def pulse_campaign_story_link(ident):
    with connection() as db:
        item=db.execute('SELECT url FROM content_blocks WHERE id=?',(ident,)).fetchone()
        if not item or not story_url_valid(item['url']):raise ValueError('URL partenaire HTTP(S) valide requise')
        story=db.execute('SELECT token FROM story_links WHERE promotion_id=?',(ident,)).fetchone()
        if story:
            channels=['instagram',*('tracked:'+value for value in tracked_links.platform_source_ids(db,'instagram'))]
            alias=db.execute('SELECT code FROM short_aliases WHERE target_token=? AND revoked=0 AND source IN ('+','.join('?' for _ in channels)+') ORDER BY created_at,rowid LIMIT 1',[story['token'],*channels]).fetchone()
            if alias:return {'url':ORIGIN+'/'+alias['code'],'code':alias['code']}
        source=tracked_links.publication_source(db,ident)
    return story_link(ident,'src_'+source['id'])


def pulse_story_link(data):
    if not isinstance(data,dict) or data.get("type") not in {"campaign","independent","youtube"}:
        raise ValueError("Type PulSe invalide")
    ident=data.get("id")
    if not isinstance(ident,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}",ident):
        raise ValueError("Identifiant PulSe invalide")
    if data["type"]=="youtube":return pulse_youtube_story_link(ident)
    if data["type"]=="campaign":
        with connection() as db:
            row=db.execute("""SELECT * FROM content_blocks
                              WHERE id=? AND type IN ('promo','featured') AND retired=0""",(ident,)).fetchone()
            if not row or status_of(row)!="Actif":
                raise ValueError("Promotion non active ou introuvable")
        # Reuse the same stable campaign Story redirect as the existing back office.
        return pulse_campaign_story_link(ident)
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        source=tracked_links.publication_source(db,ident)
        # Only independent, currently shareable links can be published.
        return tracked_links.token_link(db,ident,source["id"],ORIGIN,now_iso())


class Handler(BaseHTTPRequestHandler):

    def pulse_bridge_get(self):
        if not self.server.admin or not pulse_token_ready():return self.send(404)
        if not pulse_authenticated(self.headers.get("Authorization","")):
            return self.json(401,{"error":"Accès PulSe refusé"})
        path=urlsplit(self.path).path
        try:
            if path=="/api/pulse/link-manager":return self.json(200,pulse_manager.catalog(pulse_services()))
            if path=="/api/pulse/today":
                if urlsplit(self.path).query:raise ValueError('Aucun paramètre attendu')
                return self.json(200,pulse_today())
            if path=="/api/pulse/links":return self.json(200,pulse_links())
            if path in {"/api/pulse/stats","/api/pulse/insights"}:
                periods=parse_qs(urlsplit(self.path).query,keep_blank_values=True).get("days",["7"])
                if len(periods)!=1:raise ValueError("Une seule période PulSe est autorisée")
                return self.json(200,(pulse_insights if path.endswith('/insights') else pulse_stats)(periods[0]))
            return self.send(404)
        except ValueError as exc:
            return self.json(400,{"error":str(exc)})
        except (sqlite3.Error,OSError):
            return self.json(503,{"error":"Données PulSe indisponibles"})

    def pulse_bridge_post(self):
        if not self.server.admin or not pulse_token_ready():return self.send(404)
        if not pulse_authenticated(self.headers.get("Authorization","")):
            return self.json(401,{"error":"Accès PulSe refusé"})
        if not self.headers.get("Content-Type","").lower().startswith("application/json"):
            return self.json(415,{"error":"JSON requis"})
        try:
            path=urlsplit(self.path).path
            operations={'/api/pulse/link-preview':pulse_manager.preview,'/api/pulse/link-save':pulse_manager.save,'/api/pulse/link-token':pulse_manager.token}
            if path in operations:
                result=operations[path](pulse_services(),self.body(32768))
                return self.json(200,result)
            if path=="/api/pulse/story-link":return self.json(200,pulse_story_link(self.body(1024)))
            return self.send(404)
        except tracked_links.DuplicateDestination as exc:
            return self.json(409,{'code':'DUPLICATE','error':str(exc),'duplicates':exc.matches})
        except pulse_manager.Conflict as exc:
            return self.json(409,{'code':'REVIEW_REQUIRED','error':str(exc)})
        except (ValueError,TypeError,json.JSONDecodeError) as exc:
            return self.json(400,{"error":str(exc) or "Demande PulSe invalide"})
        except (sqlite3.Error,OSError):
            return self.json(503,{"error":"Tracking temporairement indisponible"})

    def handle_one_request(self):
        self.response_status=0
        super().handle_one_request()
        if self.server.admin and getattr(self,'command','') in {'POST','PUT','DELETE'} and 200<=self.response_status<300:
            path=urlsplit(self.path).path
            if public_mutation(path):
                CAMPAIGN_WAKE.set()
                try:storage_state()
                except (OSError,sqlite3.Error,ValueError):print('Links : suivi des fichiers temporairement indisponible.',flush=True)
            if public_mutation(path):
                try:write_public_fallback()
                except (OSError,sqlite3.Error):print('Links : actualisation du secours public indisponible.',flush=True)
    def send_response(self,code,message=None):
        self.response_status=code
        return super().send_response(code,message)
    def auth_redirect(self,path):
        self.send_response(303);self.send_header('Location',path);self.send_header('Cache-Control','no-store');self.send_header('Content-Length','0');self.end_headers()
    def request_safe(self):
        # An unguessable CSRF token protects local sessions. The custom header
        # and same-origin check also protect external-auth deployments.
        origin=self.headers.get('Origin')
        if self.headers.get('X-Links-Request')!='1':return False
        return not origin or urlsplit(origin).netloc==self.headers.get('Host')
    def authorized(self,mutation=False):
        with connection() as db:
            ready=instance.get(db,'app.setup_completed')=='true'
            mode=instance.get(db,'auth.mode','local');session=instance.session(db,self.headers)
        if not ready:
            self.json(403,{'error':'Configuration initiale requise.'});return False
        if mode=='local' and not session:
            self.json(401,{'error':'Connexion requise.'});return False
        if mutation and (not self.request_safe() or (mode=='local' and not secrets.compare_digest(self.headers.get('X-Links-CSRF',''),session['csrf']))):
            self.json(403,{'error':'Requête de sécurité invalide.'});return False
        return True
    def auth_get(self):
        path=urlsplit(self.path).path
        if path in {'/healthz','/api/public-config'} or path.startswith(('/uploads/','/assets/')):return False
        with connection() as db:
            ready=instance.get(db,'app.setup_completed')=='true';mode=instance.get(db,'auth.mode','local');session=instance.session(db,self.headers)
        if path=='/api/auth/status':
            self.json(200,{'setup_completed':ready,'mode':mode,'authenticated':ready and (mode=='external' or bool(session)),'csrf':session['csrf'] if session else ''});return True
        if path in {'/brand.svg','/brand-light.svg','/mark.svg','/brand-official.png'}:return False
        if path in {'/access.js','/access.css'}:
            self.file(ADMIN/path[1:]);return True
        if path in {'/setup','/login'}:
            if ready and (mode=='external' or session):self.auth_redirect('/')
            elif path=='/login' and not ready:self.auth_redirect('/setup')
            elif path=='/setup' and ready:self.auth_redirect('/login')
            else:self.file(ADMIN/'access.html','text/html;charset=utf-8')
            return True
        if path=='/' and (not ready or (mode=='local' and not session)):
            self.auth_redirect('/setup' if not ready else '/login');return True
        return not self.authorized()
    def auth_cookie(self,token):
        with connection() as db:origin=os.environ.get('ADMIN_ORIGIN') or instance.get(db,'site.url')
        return instance.cookie_header(token,secure=origin.startswith('https://'),clear=not token)
    def auth_reply(self,token):
        body=b'{"ok":true}';self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Set-Cookie',self.auth_cookie(token));self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def auth_post(self):
        path=urlsplit(self.path).path
        if path not in {'/api/setup','/api/setup/check','/api/auth/login','/api/auth/logout','/api/auth/access'}:return not self.authorized(mutation=True)
        if not self.request_safe():self.json(403,{'error':'Origine de requête invalide.'});return True
        try:
            data=self.body(16384)
            if path in {'/api/setup','/api/setup/check','/api/auth/login'}:
                with AUTH_LOCK:
                    now=time.monotonic();AUTH_ATTEMPTS[:]=[x for x in AUTH_ATTEMPTS if x>now-300]
                    if len(AUTH_ATTEMPTS)>=20:self.json(429,{'error':'Trop de tentatives. Réessayer dans quelques minutes.'});return True
                    AUTH_ATTEMPTS.append(now)
            with connection() as db:
                db.execute('BEGIN IMMEDIATE')
                ready=instance.get(db,'app.setup_completed')=='true'
                if path=='/api/setup/check':
                    saved=db.execute("SELECT value FROM auth_state WHERE key='bootstrap_hash'").fetchone();code=data.get('bootstrap','')
                    if ready or not isinstance(code,str) or len(code)>100 or not saved or not secrets.compare_digest(instance.digest(code),saved[0]):raise ValueError('Code de configuration invalide.')
                    self.json(200,{'ok':True});return True
                if path=='/api/setup':
                    if ready:raise ValueError('Configuration déjà terminée.')
                    saved=db.execute("SELECT value FROM auth_state WHERE key='bootstrap_hash'").fetchone()
                    code=data.get('bootstrap','')
                    if not isinstance(code,str) or len(code)>100 or not saved or not secrets.compare_digest(instance.digest(code),saved[0]):raise ValueError('Code de configuration invalide.')
                    if data.get('password')!=data.get('confirmation'):raise ValueError('Les mots de passe ne correspondent pas.')
                    values=configuration_input(data)
                    if not values.get('site.url'):raise ValueError('Adresse publique requise.')
                    first=block_data({'type':'classic','internal_name':required(data,'link_title',300),'title':required(data,'link_title',300),'url':required(data,'link_url',2048)})
                    logo=data.get('logo_upload');logo_raw=None
                    if logo is not None:
                        if not isinstance(logo,dict) or logo.get('type') not in IMAGE_TYPES or not isinstance(logo.get('data'),str):raise ValueError('Logo invalide.')
                        logo_raw=base64.b64decode(logo['data'].split(',',1)[-1],validate=True)
                        user_images.validate(logo_raw,IMAGE_TYPES[logo["type"]])
                        name=str(uuid.uuid4())+IMAGE_TYPES[logo['type']];values['profile.logo']='/uploads/'+name
                    # No writes happen until all fields and credentials validate.
                    instance.account(db,data.get('username'),data.get('password'))
                    for key,value in values.items():instance.put(db,key,value)
                    save_content(db,first)
                    instance.put(db,'auth.mode','local');instance.put(db,'app.setup_completed','true');instance.put(db,'content.initialized','1')
                    db.execute("DELETE FROM auth_state WHERE key='bootstrap_hash'")
                    token=instance.new_session(db)
                    if logo_raw is not None:
                        self.setup_upload=UPLOADS/name;storage.write(self.setup_upload,logo_raw)
                elif path=='/api/auth/login':
                    if not ready or instance.get(db,'auth.mode')!='local':raise ValueError('Connexion indisponible.')
                    row=db.execute('SELECT * FROM admin_accounts WHERE id=1').fetchone()
                    username=data.get('username','');password=data.get('password','')
                    valid=instance.password_ok(password,row['password_hash'] if row else 'pbkdf2-sha256$600000$'+('00'*24)+'$'+('00'*32))
                    if not row or not isinstance(username,str) or not secrets.compare_digest(username.encode(),row['username'].encode()) or not valid:raise ValueError('Identifiant ou mot de passe incorrect.')
                    token=instance.new_session(db)
                else:
                    current=instance.get(db,'auth.mode');session=instance.session(db,self.headers)
                    if not ready or (current=='local' and (not session or not secrets.compare_digest(data.get('csrf',''),session['csrf']))):raise ValueError('Session invalide.')
                    if path=='/api/auth/logout':
                        if session:db.execute('DELETE FROM admin_sessions WHERE token_hash=?',(session['token_hash'],))
                        token=''
                    else:
                        mode=data.get('mode')
                        if mode not in {'local','external'}:raise ValueError('Mode invalide.')
                        if mode=='external' and data.get('confirm_external') is not True:raise ValueError('Confirmer la protection externe avant de changer de mode.')
                        if current=='local':
                            old=db.execute('SELECT password_hash FROM admin_accounts WHERE id=1').fetchone()
                            if not old or not instance.password_ok(data.get('current_password',''),old[0]):raise ValueError('Mot de passe actuel incorrect.')
                        if mode=='local':
                            if data.get('password')!=data.get('confirmation'):raise ValueError('Confirmation incorrecte.')
                            instance.account(db,data.get('username'),data.get('password'))
                        instance.put(db,'auth.mode',mode);db.execute('DELETE FROM admin_sessions');token=instance.new_session(db) if mode=='local' else ''
            with connection() as db:sync_configuration(db)
            if path=='/api/setup':(DATA_DIR/'setup-code').unlink(missing_ok=True)
            self.auth_reply(token)
        except (ValueError,TypeError,KeyError,json.JSONDecodeError,binascii.Error,sqlite3.IntegrityError) as exc:
            if getattr(self,'setup_upload',None):self.setup_upload.unlink(missing_ok=True)
            self.json(400,{'error':str(exc) or 'Requête invalide.'})
        except (OSError,sqlite3.OperationalError):
            if getattr(self,'setup_upload',None):self.setup_upload.unlink(missing_ok=True)
            self.json(503,{'error':'Stockage indisponible. Configuration non terminée.'})
        return True
    def log_message(self,*_):pass
    def setup(self):super().setup();self.connection.settimeout(15)
    def send(self,status,body=b"",mime="application/json; charset=utf-8"):
        # Drain bounded request bodies before closing, including early rejection.
        # Otherwise Windows may reset the socket before the client reads the response.
        if getattr(self,'command','') in {'POST','PUT'} and not getattr(self,'body_read',False):
            try:size=int(self.headers.get('Content-Length','0'))
            except ValueError:size=0
            if 0<size<=BACKUP_LIMIT:self.rfile.read(size)
            self.body_read=True
        self.send_response(status);self.send_header("Content-Type",mime);self.send_header("Content-Length",str(len(body)));self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");self.send_header("Content-Security-Policy","default-src 'self';script-src 'self';style-src 'self';img-src 'self' data: https:;object-src 'none';frame-ancestors 'none';base-uri 'none'");self.end_headers();self.wfile.write(body)
    def json(self,status,data):self.send(status,json.dumps(data,ensure_ascii=False).encode())
    def body(self,limit=8*1024*1024):
        size=int(self.headers.get("Content-Length","0"))
        if not 0<size<=limit:raise ValueError("Corps invalide")
        raw=self.rfile.read(size);self.body_read=True
        data=json.loads(raw)
        if not isinstance(data,dict):raise ValueError("Objet attendu")
        return data
    def file(self,path,mime=None):
        try:data=path.read_bytes()
        except OSError:return self.send(404)
        self.send(200,data,mime or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
    def do_GET(self):
        if urlsplit(self.path).path.startswith("/api/pulse/"):
            return self.pulse_bridge_get()
        if self.server.admin and self.auth_get():return
        url=urlsplit(self.path)
        if self.server.admin and url.path == "/brand-official.png":return self.file(ADMIN/"brand-official.png","image/png")
        if self.server.admin and url.path in {"/brand.svg","/brand-light.svg","/mark.svg"}:return self.file(ADMIN/url.path[1:],"image/svg+xml")
        if url.path.startswith('/go/'):
            token=url.path.removeprefix('/go/')
            return self.redirect_tracked(token) if tracked_links.TOKEN.fullmatch(token) else self.redirect_story(token)
        if short_urls.CODE.fullmatch(url.path[1:]):
            return self.redirect_short(url.path[1:])
        if url.path=="/latest-video.json":
            try:return self.json(200,latest_video())
            except (OSError,ValueError):return self.json(502,{"error":"Vidéo momentanément indisponible"})
        if url.path=="/healthz":
            try:
                with connection() as db:db.execute("SELECT total FROM counts LIMIT 1").fetchone()
                return self.send(200,b"ok","text/plain")
            except (sqlite3.Error,OSError):return self.send(503)
        if self.server.admin and url.path.startswith("/preview/assets/"):
            name=url.path.removeprefix("/preview/assets/")
            if not re.fullmatch(r"[A-Za-z0-9._-]+",name):return self.send(404)
            return self.file(STATIC/"assets"/name)
        if url.path.startswith("/assets/"):
            name=url.path.removeprefix("/assets/")
            if not re.fullmatch(r"[A-Za-z0-9._-]+",name):return self.send(404)
            target=DATA_DIR/"assets"/name
            return self.file(target if target.is_file() else STATIC/"assets"/name)
        if url.path.startswith("/uploads/"):
            name=unquote(url.path.removeprefix("/uploads/"))
            return self.file(UPLOADS/name) if re.fullmatch(r"[a-f0-9-]{36}\.(jpg|png|webp|gif)",name) else self.send(404)
        if not self.server.admin:return self.json(200,public_config()) if url.path=="/api/public-config" else self.send(404)
        try:
            if url.path.startswith("/api/descriptions/"):
                with connection() as db:return self.json(200,descriptions.read(db,url.path.removeprefix("/api/descriptions/"),ORIGIN))
            if url.path.startswith("/api/affiliation/"):
                return self.json(200,affiliation.get(connection,url.path.removeprefix("/api/affiliation/"),{k:v[0] for k,v in parse_qs(url.query).items()}))
            if url.path=="/api/appearance":
                with connection() as db:return self.json(200,themes.state(db))
            if url.path=='/api/appearance/campaign-image':
                with connection() as db:return self.json(200,campaign_image_settings(db))
            if url.path=="/api/appearance/export":
                with connection() as db:
                    target=parse_qs(url.query).get("id",[themes.ORIGINAL])[0]
                    theme=next((x for x in themes.state(db)["items"] if x["id"]==target),None)
                    if theme is None:raise ValueError("Thème introuvable")
                    return self.json(200,themes.export(theme,UPLOADS))
            if url.path=="/api/youtube":return self.json(200,youtube_status())
            if url.path=="/api/quotes":return self.json(200,{"items":quote_list()})
            if url.path=="/api/tracking-sources":
                with connection() as db:return self.json(200,{"items":tracked_links.source_rows(db)})
            if url.path=="/api/affiliate-partners":
                with connection() as db:return self.json(200,{"items":affiliate_partners.rows(db)})
            if url.path=="/api/tracked-links":
                with connection() as db:
                    q=parse_qs(url.query)
                    return self.json(200,{"items":affiliate_partners.list_tracked(db,q.get("start",[None])[0],q.get("end",[None])[0])})
            if url.path=="/api/backup":return self.send(200,export_backup())
            if url.path=="/api/storage":return self.json(200,storage_state())
            if url.path=="/api/stats":
                q=parse_qs(url.query);today=datetime.now(PARIS).date();return self.json(200,report(q.get("start",[(today-timedelta(days=29)).isoformat()])[0],q.get("end",[today.isoformat()])[0],q.get("source",[""])[0]))
            if url.path=="/api/page-layout":
                with connection() as db:return self.json(200,page_layout(db))
            if url.path=="/api/content":return self.json(200,{"items":content_list(parse_qs(url.query).get("archived",["0"])[0]=="1")})
            if url.path=="/api/promotions/selection":
                values=parse_qs(url.query,keep_blank_values=True).get('at',[None])
                if len(values)!=1 or values[0]=='':raise ValueError('Une seule date de sélection est requise')
                return self.json(200,campaign_selection(values[0]))
            if url.path=="/api/buttons":return self.json(200,{"items":button_list(parse_qs(url.query).get('archived',['0'])[0]=='1')})
            if url.path=="/api/settings/overview":
                with connection() as db:
                    sizes=storage.summary(db,UPLOADS,DATA_DIR/'assets')
                    configured=bool(instance.get(db,'profile.name') and instance.get(db,'site.url'))
                    count=db.execute('SELECT COUNT(*) FROM footer_quotes').fetchone()[0]
                video=youtube_status()
                return self.json(200,{'identity':configured,'youtube':video['configured'],'analytics':analytics_enabled(),'quotes':count,'storage':sizes})
            if url.path=="/api/settings":
                with connection() as db:return self.json(200,profile(db))
            if url.path=="/api/public-config":return self.json(200,public_config())
        except (ValueError,TypeError) as exc:return self.json(400,{"error":str(exc) or "Paramètres invalides"})
        except (OSError,sqlite3.Error):return self.json(503,{"error":"Stockage temporairement indisponible."})
        if url.path=="/preview/cards.js":return self.file(STATIC/"cards.js","application/javascript")
        if url.path=="/preview/icons.css":return self.file(STATIC/"icons.css","text/css")
        if url.path=="/preview/style.css":return self.file(ROOT/"site"/"style.css" if (ROOT/"site"/"style.css").exists() else Path("/usr/share/nginx/html/style.css"),"text/css")
        if url.path=="/preview/preview.css":return self.file(ADMIN/"promo-preview.css","text/css")
        if url.path.startswith("/preview/") and url.path[9:] in {"index.html","app.js","config.js","metrics.js","theme.js","theme.css","theme-tokens.json","asset-library.json"}:return self.file(STATIC/url.path[9:])
        if url.path in {"/uuid.js","/description-workflow.js","/description-search.js","/description-analysis.js","/description-sections.js","/description-editor.js","/descriptions.js","/descriptions.css","/affiliation.js","/affiliation.css","/collection.js","/partner-report.js","/source-platforms.js","/daily-report.js","/charts.js","/navigation.js","/page-editor.js","/page-editor.css","/page-editor-preview.css","/appearance.js","/appearance.css","/shortcuts.js","/uploads.js","/storage.js","/settings.js","/tracking.js","/title-batch.js","/link-batch.js","/theme-init.js"}:return self.file(ADMIN/url.path[1:])
        files={"/":("index.html","text/html;charset=utf-8"),"/app.js":("app.js","application/javascript"),"/dates.js":("dates.js","application/javascript"),"/calendar.js":("calendar.js","application/javascript"),"/style.css":("style.css","text/css")}
        return self.file(ADMIN/files[url.path][0],files[url.path][1]) if url.path in files else self.send(404)
    def do_POST(self):
        if urlsplit(self.path).path.startswith("/api/pulse/"):
            return self.pulse_bridge_post()
        if self.server.admin and self.auth_post():return
        path=urlsplit(self.path).path
        if not self.server.admin:
            if path!="/metrics":return self.send(404)
            if not analytics_enabled():return self.send(204)
            if self.headers.get("Origin")!=ORIGIN:return self.send(403)
            if not collection_allowed(self.headers):return self.send(204)
            try:
                data=self.body(2048);kind,key=data.get("kind"),data.get("link","")
                if kind=="promo_code_copy":record_promo_copy(data);return self.send(204)
                if kind not in {"view","click","impression"} or not isinstance(key,str):raise ValueError()
                record(kind,source_of(data),key if kind in {"click","impression"} else "",validate=True);return self.send(204)
            except (ValueError,TypeError,json.JSONDecodeError):return self.send(400)
            except (sqlite3.Error,OSError):return self.send(503)
        try:
            data=self.body(BACKUP_LIMIT if path in {'/api/restore','/api/restore/preview'} else themes.MAX_BYTES if path=="/api/appearance/import" else 8*1024*1024)
            if path.startswith("/api/descriptions/"):
                comparison_match=re.fullmatch(r'/api/descriptions/drafts/([\w-]+)/compare',path)
                if comparison_match:
                    import description_workflow
                    with connection() as db:return self.json(200,description_workflow.compare(db,comparison_match[1],data,ORIGIN))
                merchant_match=re.fullmatch(r'/api/descriptions/drafts/([\w-]+)/(search|prepare)',path)
                if merchant_match:
                    import description_search
                    operation=description_search.search_product if merchant_match[2]=='search' else description_search.prepare_link
                    with connection() as db:return self.json(200,operation(db,merchant_match[1],data,ORIGIN))
                analysis_match=re.fullmatch(r'/api/descriptions/drafts/([\w-]+)/analyze',path)
                if analysis_match:
                    with connection() as db:return self.json(200,descriptions.analyze_draft(db,analysis_match[1],data,ORIGIN))
                with connection() as db:
                    db.execute("BEGIN IMMEDIATE")
                    result=descriptions.write(db,path.removeprefix("/api/descriptions/"),data,ORIGIN,story_url_valid)
                return self.json(200,result)  # Acknowledge only after the transaction commits.
            if path.startswith("/api/affiliation/"):
                return self.json(200,affiliation.post(connection,path.removeprefix("/api/affiliation/"),data))
            if path=="/api/appearance/css":return self.json(200,themes.css_import(data.get("css")))
            if path=='/api/appearance/campaign-image':return self.json(200,save_campaign_image(data))
            if path=="/api/appearance/css-export":return self.json(200,{'css':themes.css_export(themes.record(data.get('theme')))})
            if path=="/api/appearance":
                with connection() as db:result=themes.save(db,data,UPLOADS)
                return self.json(200,result)
            if path=="/api/appearance/import":
                with connection() as db:result=themes.import_package(db,data,UPLOADS)
                return self.json(201,result)
            if path=="/api/youtube/test":return self.json(200,youtube_test(data))
            if path=="/api/youtube":return self.json(200,save_youtube(data))
            if path=="/api/quotes/analyze":return self.json(200,add_quotes(data,preview=True))
            if path=="/api/quotes":return self.json(200,add_quotes(data))
            if path=="/api/restore":return self.json(200,restore_backup(data))
            if path=="/api/restore/preview":return self.json(200,restore_backup(data,preview=True))
            if path=="/api/promotions/replace":return self.replace_promotion(data)
            if path=="/api/tracking-sources":
                with connection() as db:return self.json(201,tracked_links.add_source(db,data,now_iso()))
            if path=="/api/affiliate-partners/preview":
                fields=affiliate_partners.partner_input(data)
                return self.json(200,{"url":affiliate_partners.build_url(fields['template'],fields['code'],data.get('test_url',''))})
            if path=="/api/affiliate-partners":
                with connection() as db:return self.json(201,affiliate_partners.save(db,data,now_iso()))
            if path=="/api/tracked-links/batch/preview":
                with connection() as db:
                    return self.json(200,tracked_batch.preview_many(db,data,story_url_valid))
            if path=="/api/tracked-links/batch/create":
                with connection() as db:
                    db.execute('BEGIN IMMEDIATE')
                    return self.json(201,tracked_batch.create_many(db,data,story_url_valid,now_iso()))
            if path=="/api/tracked-links/titles/bulk-update":
                with connection() as db:
                    db.execute('BEGIN IMMEDIATE')
                    return self.json(200,tracked_links.update_titles(db,data,now_iso()))
            if path=="/api/tracked-links/title-preview":
                if not isinstance(data,dict):raise ValueError('Requête invalide.')
                original=tracked_links.text_field(data,'url',2000,True)
                if not story_url_valid(original):raise ValueError('URL d’origine HTTP(S) valide, extérieure à LinKs, requise.')
                current_title=tracked_links.text_field(data,'current_title',160)
                return self.json(200,url_inspection.suggest_title(original,current_title=current_title,
                                                                 url_validator=story_url_valid))
            if path=="/api/tracked-links":
                with connection() as db:
                    db.execute('BEGIN IMMEDIATE')
                    return self.json(201,affiliate_partners.save_tracked(db,data,story_url_valid,now_iso()))
            if path=="/api/tracked-links/preview":
                ident=tracked_links.text_field(data,'link_id',32)
                if ident and not tracked_links.IDENT.fullmatch(ident):raise ValueError('Identifiant de lien invalide')
                with connection() as db:return self.json(200,affiliate_partners.preview_tracked(db,data,ident or None,story_url_valid))
            match=re.fullmatch(r"/api/tracked-links/([a-f0-9]{32})/check-destination",path)
            if match:
                # Only inspect the stored affiliate destination, never a client URL.
                # Release the database connection before any network operation.
                with connection() as db:
                    link=db.execute('SELECT url FROM tracked_links WHERE id=?',(match.group(1),)).fetchone()
                if not link:return self.json(404,{'error':'Lien introuvable.'})
                return self.json(200,url_inspection.check_destination(link['url'],url_validator=story_url_valid))
            match=re.fullmatch(r"/api/tracked-links/([a-f0-9]{32})/token",path)
            if match:
                with connection() as db:
                    db.execute('BEGIN IMMEDIATE')
                    return self.json(200,tracked_links.token_link(db,match.group(1),data.get('source_id'),ORIGIN,now_iso()))
            match=re.fullmatch(r"/api/tracked-links/([a-f0-9]{32})/(archive|restore|disable|enable)",path)
            if match:
                flag="archived" if match.group(2) in {"archive","restore"} else "enabled"
                value=match.group(2) in {"archive","enable"}
                with connection() as db:return self.json(200,tracked_links.set_link_flag(db,match.group(1),flag,value))
            match=re.fullmatch(r"/api/tracking-sources/([a-f0-9]{32})/restore",path)
            if match:
                with connection() as db:return self.json(200,tracked_links.restore_source(db,match.group(1)))
            if path=='/api/content/preview':
                ident=data.get('id') or None
                if ident is not None and (not isinstance(ident,str) or len(ident)>100):raise ValueError('Identifiant de campagne invalide')
                with connection() as db:return self.json(200,affiliate_partners.preview_campaign(db,data,ident,valid_url))
            if path=="/api/page-layout":return self.json(200,save_page_layout(data))
            if path=="/api/content":return self.create_content(data)
            if path=="/api/promotions/check":
                item=block_data(data);return self.json(200,promotion_check(item,data.get("id") or None))
            if path=="/api/content/reorder":return self.reorder("content_blocks",data)
            match=re.fullmatch(r"/api/content/([\w-]+)/story-link",path)
            if match:return self.json(200,story_link(match.group(1),data.get("source") if "source" in data else None))
            match=re.fullmatch(r"/api/content/([\w-]+)/(duplicate|archive|restore)",path)
            if match:return self.content_action(match.group(1),match.group(2))
            if path=="/api/buttons":return self.create_button(data)
            match=re.fullmatch(r'/api/buttons/([\w-]+)/restore',path)
            if match:
                with connection() as db:
                    changed=db.execute('UPDATE top_buttons SET retired=0,active=1,updated_at=? WHERE id=?',(now_iso(),match.group(1))).rowcount
                return self.send(204) if changed else self.send(404)
            if path=="/api/buttons/reorder":return self.reorder("top_buttons",data)
            if path=="/api/upload":return self.upload(data)
            if path=="/api/storage":
                action=data.get('action')
                if action not in {'cleanup','empty'}:raise ValueError('Action de stockage inconnue')
                return self.json(200,storage_state(action))
            if path=="/api/settings":return self.save_settings(data)
            return self.send(404)
        except descriptions.Conflict as exc:return self.json(409,{"error":str(exc),"conflict":True})
        except tracked_links.DuplicateDestination as exc:return self.json(409,{"error":str(exc),"duplicates":exc.matches})
        except (ValueError,TypeError,json.JSONDecodeError,binascii.Error,sqlite3.IntegrityError) as exc:return self.json(400,{"error":str(exc) or "Requête invalide"})
        except (OSError,sqlite3.OperationalError):return self.json(503,{"error":"Stockage indisponible. Les données n’ont pas été remplacées."})
    def do_PUT(self):
        if self.server.admin and not self.authorized(mutation=True):return
        if not self.server.admin:return self.send(404)
        try:
            data=self.body();path=urlsplit(self.path).path
            match=re.fullmatch(r"/api/quotes/([\w-]+)",path)
            if match:
                if type(data.get("active")) is not bool:raise ValueError("active doit être un booléen")
                with connection() as db:changed=db.execute("UPDATE footer_quotes SET active=? WHERE id=?",(int(data["active"]),match.group(1))).rowcount
                return self.send(204) if changed else self.send(404)
            match=re.fullmatch(r"/api/tracked-links/([a-f0-9]{32})",path)
            if match:
                with connection() as db:
                    db.execute('BEGIN IMMEDIATE')
                    return self.json(200,affiliate_partners.save_tracked(db,data,story_url_valid,now_iso(),match.group(1)))
            match=re.fullmatch(r"/api/tracking-sources/([a-f0-9]{32})",path)
            if match:
                with connection() as db:return self.json(200,tracked_links.edit_source(db,match.group(1),data))
            match=re.fullmatch(r"/api/affiliate-partners/([a-f0-9]{32})",path)
            if match:
                with connection() as db:return self.json(200,affiliate_partners.save(db,data,now_iso(),match.group(1)))
            match=re.fullmatch(r"/api/content/([\w-]+)",path)
            if match:return self.update_content(match.group(1),data)
            match=re.fullmatch(r"/api/buttons/([\w-]+)",path)
            if match:return self.update_button(match.group(1),data)
            return self.send(404)
        except tracked_links.DuplicateDestination as exc:return self.json(409,{"error":str(exc),"duplicates":exc.matches})
        except (ValueError,TypeError,json.JSONDecodeError) as exc:return self.json(400,{"error":str(exc) or "Requête invalide"})
    def do_DELETE(self):
        if self.server.admin and not self.authorized(mutation=True):return
        if not self.server.admin:return self.send(404)
        path=urlsplit(self.path).path
        match=re.fullmatch(r"/api/affiliate-partners/([a-f0-9]{32})",path)
        if match:
            try:
                with connection() as db:return self.json(200,affiliate_partners.remove(db,match.group(1)))
            except ValueError as exc:return self.json(409,{"error":str(exc)})
        match=re.fullmatch(r"/api/tracking-sources/([a-f0-9]{32})",path)
        if match:
            try:
                with connection() as db:return self.json(200,tracked_links.remove_source(db,match.group(1)))
            except ValueError as exc:return self.json(400,{"error":str(exc)})
        if path=="/api/quotes":
            with connection() as db:db.execute("DELETE FROM footer_quotes")
            return self.send(204)
        quote=re.fullmatch(r"/api/quotes/([\w-]+)",path)
        if quote:
            with connection() as db:changed=db.execute("DELETE FROM footer_quotes WHERE id=?",(quote.group(1),)).rowcount
            return self.send(204) if changed else self.send(404)
        match=re.fullmatch(r"/api/content/([\w-]+)",path);table="content_blocks"
        if not match:match=re.fullmatch(r"/api/buttons/([\w-]+)",path);table="top_buttons"
        if not match:return self.send(404)
        with connection() as db:
            state='archived=1' if table=='content_blocks' else 'active=0'
            changed=db.execute(f"UPDATE {table} SET retired=1,{state},updated_at=? WHERE id=?",(now_iso(),match.group(1))).rowcount
        return self.send(204) if changed else self.send(404)
    def do_HEAD(self):
        path=urlsplit(self.path).path
        if short_urls.CODE.fullmatch(path[1:]):
            return self.redirect_short(path[1:],count=False)
        if not path.startswith('/go/'):return self.send(404)
        token=path.removeprefix('/go/')
        return self.redirect_tracked(token,count=False) if tracked_links.TOKEN.fullmatch(token) else self.redirect_story(token,count=False)
    def redirect_short(self,code,count=True):
        try:
            with connection() as db:alias=short_urls.lookup(db,code)
            if not alias:return self.send(404)
            if alias['revoked']:return self.send(410)
            token=alias['target_token']
            if token.startswith('tk_'):return self.redirect_tracked(token,count=count)
            return self.redirect_story(token,count=count,source_override=alias['source'])
        except (sqlite3.Error,OSError):return self.send(503)
    def redirect_tracked(self,token,count=True):
        try:
            with connection() as db:
                db.execute('BEGIN IMMEDIATE')
                row=tracked_links.find_destination(db,token)
                if not row:return self.send(404)
                if not row['enabled'] or not story_url_valid(row['url']):return self.send(410)
                if count and instance.get(db,"analytics.enabled")=="true" and collection_allowed(self.headers):
                    now=datetime.now(PARIS)
                    increment(db,'tracked','tracked:'+row['source_id'],'tracked:'+token+':'+now.strftime('%H'),now.date().isoformat())
                    tracked_links.count_click(db,token)
                target=story_destination(row['url'])
            self.send_response(302);self.send_header('Location',target);self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Length','0');self.end_headers()
        except (sqlite3.Error,OSError):return self.send(503)
    def redirect_story(self,token,count=True,source_override=None):
        if not STORY_TOKEN.fullmatch(token):return self.send(404)
        try:
            with connection() as db:
                db.execute('BEGIN IMMEDIATE')
                item=db.execute('''SELECT b.url,b.internal_name,s.deleted FROM story_links s
                  LEFT JOIN content_blocks b ON b.id=s.promotion_id WHERE s.token=?''',(token,)).fetchone()
                if not item:return self.send(404)
                if item['deleted'] or not item['url']:return self.send(410)
                if not story_url_valid(item['url']):return self.send(410)
                if count and instance.get(db,"analytics.enabled")=="true" and collection_allowed(self.headers):
                    now=datetime.now(PARIS)
                    source=source_override if source_override is not None else parse_qs(urlsplit(self.path).query).get('utm_source',[''])[0].strip().lower()
                    if source_override is not None:pass
                    elif re.fullmatch(r'src_[a-f0-9]{32}',source):
                        ref=source[4:]
                        source='tracked:'+ref if db.execute("SELECT 1 FROM tracking_sources WHERE id=?",(ref,)).fetchone() else 'shared-unknown'
                    elif source not in {'instagram','youtube','facebook','tiktok','discord','newsletter','site','mail','qr'}:source='shared-unknown'
                    increment(db,'story',source,'story:'+token+':'+now.strftime('%H'),now.date().isoformat())
                    tracked_links.count_campaign_source(db,source)
                target=story_destination(item['url'])
            self.send_response(302);self.send_header('Location',target);self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Length','0');self.end_headers()
        except (sqlite3.Error,OSError):return self.send(503)
    def create_content(self,data):
        with connection() as db:
            db.execute("BEGIN IMMEDIATE")
            item_id=save_content_request(db,data)
        return self.json(201,{"id":item_id})
    def update_content(self,item_id,data):
        with connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute('SELECT 1 FROM content_blocks WHERE id=?',(item_id,)).fetchone():return self.send(404)
            save_content_request(db,data,item_id)
        return self.send(204)
    def replace_promotion(self,data):
        target=required(data,"replace_id",100)
        content=data.get("content")
        if not isinstance(content,dict):raise ValueError("Promotion invalide")
        item=block_data(content);item_id=content.get("id") or None
        if item["type"] not in {"promo","featured"} or item_id==target:raise ValueError("Remplacement invalide")
        with connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT * FROM content_blocks WHERE id=? AND archived=0 AND type IN ('promo','featured')",(target,)).fetchone()
            if not row:raise ValueError("Promotion à remplacer introuvable")
            db.execute("UPDATE content_blocks SET active=0,updated_at=? WHERE id=?",(now_iso(),target))
            item_id=save_content_request(db,content,item_id)
        return self.json(200,{"id":item_id})
    def content_action(self,item_id,action):
        with connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT * FROM content_blocks WHERE id=?",(item_id,)).fetchone()
            if not row:return self.send(404)
            if action=="duplicate":
                new_id=str(uuid.uuid4());stamp=now_iso();pos=db.execute("SELECT COALESCE(MAX(position),-1)+1 FROM content_blocks").fetchone()[0]
                db.execute("""INSERT INTO content_blocks(id,type,internal_name,title,description,url,icon,image,badge,cta,position,active,draft,start_at,end_at,archived,created_at,updated_at,priority)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(new_id,row["type"],row["internal_name"]+" (copie)",row["title"],row["description"],row["url"],row["icon"],row["image"],row["badge"],row["cta"],pos,0,1,row["start_at"],row["end_at"],0,stamp,stamp,row["priority"]));db.execute('UPDATE content_blocks SET promo_code=? WHERE id=?',(row['promo_code'],new_id))
                db.execute('INSERT INTO campaign_partners SELECT ?,partner_id,original_url,? FROM campaign_partners WHERE campaign_id=?',(new_id,row['url'],item_id))
                timed=json.loads(instance.get(db,'admin.calendar_timed') or '[]')
                if item_id in timed:instance.put(db,'admin.calendar_timed',json.dumps(timed+[new_id]))
                return self.json(201,{"id":new_id})
            db.execute("UPDATE content_blocks SET archived=?,retired=0,updated_at=? WHERE id=?",(1 if action=="archive" else 0,now_iso(),item_id))
        return self.send(204)
    def reorder(self,table,data):
        ids=data.get("ids")
        if not isinstance(ids,list) or not ids or (table!='content_blocks' and len(ids)>500) or len(set(ids))!=len(ids):raise ValueError("Ordre invalide")
        with connection() as db:
            for pos,item_id in enumerate(ids):
                if not db.execute(f"SELECT 1 FROM {table} WHERE id=?",(item_id,)).fetchone():raise ValueError("Élément inconnu")
                db.execute(f"UPDATE {table} SET position=?,updated_at=? WHERE id=?",(pos,now_iso(),item_id))
        return self.send(204)
    def create_button(self,data):
        item=button_data(data)
        item_id=str(uuid.uuid4());stamp=now_iso()
        with connection() as db:
            storage.require_file(UPLOADS,item["custom_icon"],db,DATA_DIR/"assets",STATIC/"assets")
            pos=db.execute("SELECT COALESCE(MAX(position),-1)+1 FROM top_buttons").fetchone()[0];db.execute("INSERT INTO top_buttons(id,icon,label,url,position,active,created_at,updated_at,custom_icon) VALUES(?,?,?,?,?,?,?,?,?)",(item_id,item["icon"],item["label"],item["url"],pos,item["active"],stamp,stamp,item["custom_icon"]))
        return self.json(201,{"id":item_id})
    def update_button(self,item_id,data):
        item=button_data(data)
        with connection() as db:
            storage.require_file(UPLOADS,item["custom_icon"],db,DATA_DIR/"assets",STATIC/"assets")
            changed=db.execute("UPDATE top_buttons SET icon=?,label=?,url=?,active=?,updated_at=?,custom_icon=? WHERE id=?",(item["icon"],item["label"],item["url"],item["active"],now_iso(),item["custom_icon"],item_id)).rowcount
        return self.send(204) if changed else self.send(404)
    def upload(self,data):
        if data.get('purpose')=='campaign-default' and data.get('type') not in {'image/png','image/jpeg','image/webp'}:
            raise ValueError('PNG, JPEG ou WebP uniquement pour le visuel par défaut')
        mime=data.get("type","");encoded=data.get("data","")
        if mime not in IMAGE_TYPES or not isinstance(encoded,str):raise ValueError("Format d’image non pris en charge")
        raw=base64.b64decode(encoded.split(",",1)[-1],validate=True)
        if not raw or len(raw)>4*1024*1024:raise ValueError("Image vide ou supérieure à 4 Mo")
        user_images.validate(raw,IMAGE_TYPES[mime],1024*1024 if data.get("purpose")=="icon" else user_images.MAX_BYTES)
        name=str(uuid.uuid4())+IMAGE_TYPES[mime]
        with connection() as db:
            storage.write(UPLOADS/name,raw)
            storage.scan(db,UPLOADS,assets=DATA_DIR/'assets',system_assets=STATIC/'assets')
        return self.json(201,{"url":"/uploads/"+name})
    def save_settings(self,data):
        values=configuration_input(data)
        with connection() as db:
            for key in ["profile.logo","profile.avatar"]:storage.require_file(UPLOADS,values.get(key),db,DATA_DIR/"assets",STATIC/"assets")
            for key,value in values.items():instance.put(db,key,value)
            sync_configuration(db)
        return self.send(204)


def serve(port,admin,host):
    server=ThreadingHTTPServer((host,port),Handler);server.admin=admin;return server
if __name__=="__main__":
    init();threading.Thread(target=affiliation.scheduler,args=(connection,),daemon=True).start();write_public_fallback();threading.Thread(target=campaign_worker,daemon=True).start();threading.Thread(target=storage_worker,daemon=True).start();public=serve(3003,False,"127.0.0.1");threading.Thread(target=public.serve_forever,daemon=True).start();serve(8081,True,"0.0.0.0").serve_forever()
