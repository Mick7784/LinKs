"""Small SQLite content manager and aggregate analytics service."""
import base64, binascii, json, mimetypes, os, re, secrets, sqlite3, threading, uuid, sys, time, shutil
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parent))
import instance
import youtube
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent
if not (ROOT/"links.json").exists(): ROOT=ROOT.parent
DB=os.environ.get("ANALYTICS_DB","/data/analytics.db")
ORIGIN=os.environ.get("ANALYTICS_ORIGIN","").rstrip("/")
ADMIN=ROOT/"admin"; UPLOADS=Path(os.environ.get("UPLOAD_DIR","/data/uploads"))
CONFIG=json.loads((ROOT/"links.json").read_text(encoding="utf-8"))
DATA_LOCK=threading.RLock()
PARIS=ZoneInfo("UTC")
DATA_DIR=Path(DB).parent
STATIC=ROOT/"site" if (ROOT/"site").exists() else Path("/usr/share/nginx/html")
AUTH_ATTEMPTS=[]
AUTH_LOCK=threading.Lock()
TYPES={"classic","promo","featured"}; ICONS={"youtube","instagram","tiktok","discord","mail","website","cart","home","amazon","facebook","x","linkedin","github","threads","twitch","telegram","whatsapp","pinterest","reddit","snapchat","network","contact","link"}
BADGES={"","Promo","Nouveau","Partenaire","Bon plan"}
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
def instant(value):
    if not value:return None
    if not isinstance(value,str):raise ValueError("Date invalide")
    try:
        result=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
        return (result if result.tzinfo else result.replace(tzinfo=PARIS)).astimezone(timezone.utc)
    except ValueError as exc: raise ValueError("Date invalide") from exc
def legacy_expiry(value):
    if value is None:return None
    if isinstance(value,(int,float)):return datetime.fromtimestamp(value/1000,timezone.utc).isoformat().replace("+00:00","Z")
    try:return instant(value).isoformat().replace("+00:00","Z")
    except ValueError:return None

def init():
    global ORIGIN,PARIS
    Path(DB).parent.mkdir(parents=True,exist_ok=True); UPLOADS.mkdir(parents=True,exist_ok=True)
    existed=Path(DB).exists() and Path(DB).stat().st_size>0
    if existed:
        with sqlite3.connect(DB) as before:
            tables={r[0] for r in before.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            legacy="settings" in tables and not before.execute("SELECT 1 FROM settings WHERE key='app.config_schema_version'").fetchone()
            if legacy:
                target=DATA_DIR/"pre-v11-database.db"
                if not target.exists():
                    with sqlite3.connect(target) as backup:before.backup(backup)
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
        db.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        db.execute("""CREATE TABLE IF NOT EXISTS story_links(
          token TEXT PRIMARY KEY,promotion_id TEXT NOT NULL UNIQUE,name TEXT NOT NULL,
          created_at TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0)""")
        db.execute("CREATE TABLE IF NOT EXISTS footer_quotes(id TEXT PRIMARY KEY,text TEXT NOT NULL UNIQUE,active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),created_at TEXT NOT NULL)")
        instance.initialize(db,legacy,CONFIG,[DATA_DIR/"assets",STATIC/"assets"],DATA_DIR)
        init_version(db)
        ORIGIN=instance.site_url(instance.get(db,"site.url"),allow_empty=True)
        PARIS=ZoneInfo(instance.get(db,"app.timezone","UTC"))

def checked_version(value):
    if not isinstance(value,str) or not re.fullmatch(r"V[0-9]+\.[0-9]+",value) or len(value)>40:
        raise ValueError("Format attendu : V1.2, V1.201 ou V2.1")
    return value

def init_version(db):
    release=os.environ.get("APP_RELEASE_VERSION") or (ROOT/"VERSION").read_text().strip()
    release_id=os.environ.get("APP_RELEASE_ID") or "bundled:"+release
    if release:checked_version(release)
    db.execute("INSERT OR IGNORE INTO settings VALUES('app.version',?)",(release or (ROOT/"VERSION").read_text().strip(),))
    applied=db.execute("SELECT value FROM settings WHERE key='app.release_id'").fetchone()
    if release and release_id and (not applied or applied[0]!=release_id):
        db.execute("INSERT INTO settings VALUES('app.version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(release,))
        db.execute("INSERT INTO settings VALUES('app.release_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(release_id,))

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
        row=db.execute("SELECT id,internal_name,type FROM content_blocks WHERE id=?",(key[6:],)).fetchone()
        if not row or row["type"] not in {"promo","featured"}:raise ValueError()
        stamp=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0).isoformat()
        snapshot=json.dumps({"id":row["id"],"name":row["internal_name"],"code":code,"timestamp":stamp},sort_keys=True,ensure_ascii=False)
        increment(db,"promo_code_copy",source_of(data),snapshot,datetime.now(PARIS).date().isoformat())

def record(kind,source,link,day=None):
    if not analytics_enabled():return
    day=day or datetime.now(PARIS).date().isoformat()
    with connection() as db:
        increment(db,kind,source,link,day)
def increment(db,kind,source,link,day):
    db.execute("INSERT INTO counts VALUES(?,?,?,?,1) ON CONFLICT(day,source,kind,link) DO UPDATE SET total=total+1",(day,source,kind,link))
    db.execute("DELETE FROM counts WHERE day < ?",((date.fromisoformat(day)-timedelta(days=400)).isoformat(),))
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
        if source and source not in {'instagram','instagram-story'}:story_where+=" AND 0"
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
    return {"rows":rows,"stories":stories,"promo_code_copies":copies,"campaign_metrics":campaign_metrics,"timezone":str(PARIS)}

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

def story_link(promotion_id):
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
        return {'url':ORIGIN+'/go/'+link['token']}

def profile(db):
    values=instance.settings(db)
    return {**{k:values.get("profile."+k,"") for k in ["name","tagline","description","avatar","logo"]},
      "content_order":json.loads(values.get("admin.content_order",'["classic","video","highlight"]')),
      "app_version":values.get("app.version",""),"footer_owner":values.get("footer.owner",values.get("profile.name","")),
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
def serialize(row,totals=None):
    item=dict(row); item.update(active=bool(item["active"]),draft=bool(item["draft"]),archived=bool(item["archived"]),status=status_of(row))
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
        clicks=totals(db); timed=json.loads(instance.get(db,"admin.calendar_timed") or "[]"); return [{**serialize(r,clicks),"calendar_timed":r["id"] in timed} for r in db.execute("SELECT * FROM content_blocks WHERE archived=? ORDER BY CASE WHEN type IN ('promo','featured') THEN 0 ELSE 1 END,position,created_at",(1 if archived else 0,))]
def button_list():
    with connection() as db:
        clicks=totals(db); result=[]
        for row in db.execute("SELECT * FROM top_buttons ORDER BY position,created_at"):
            item=dict(row);item["active"]=bool(item["active"]);item["clicks"]=clicks.get(("click","button:"+item["id"]),0);result.append(item)
        return result
def public_config():
    with connection() as db:
        blocks=[serialize(r) for r in db.execute("SELECT * FROM content_blocks WHERE archived=0 ORDER BY CASE WHEN type IN ('promo','featured') THEN 0 ELSE 1 END,CASE WHEN priority='high' THEN 0 ELSE 1 END,position,created_at") if status_of(r)=="Actif"]
        quote=db.execute("SELECT text FROM footer_quotes WHERE active=1 ORDER BY RANDOM() LIMIT 1").fetchone()
        buttons=[dict(r) for r in db.execute("SELECT * FROM top_buttons WHERE active=1 ORDER BY position,created_at")]
        result={"profile":profile(db),"socials":[{"id":x["id"],"platform":x["icon"],"label":x["label"],"url":x["url"],"metricKey":"button:"+x["id"]} for x in buttons],
                "links":[{"id":x["id"],"type":x["type"],"title":x["title"],"description":x["description"],"url":x["url"],"icon":x["icon"],"image":x["image"],"badge":x["badge"],"cta":x["cta"],"priority":x["priority"],"start_at":x["start_at"],"end_at":x["end_at"],"promo_code":x["promo_code"],"metricKey":"block:"+x["id"]} for x in blocks]}
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
        temporary=DATA_DIR/'public-fallback.tmp';target=DATA_DIR/'public-fallback.json'
        temporary.write_text(json.dumps(public_config(),ensure_ascii=False),encoding='utf-8')
        temporary.replace(target)


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
def block_data(data):
    kind=data.get("type","classic")
    if "calendar_timed" in data and not isinstance(data["calendar_timed"],bool):raise ValueError("Mode horaire invalide")
    if kind not in TYPES:raise ValueError("Type invalide")
    url=required(data,"url",2000)
    if not valid_url(url):raise ValueError("URL invalide")
    icon=data.get("icon","website"); badge=optional(data,"badge",40); image=optional(data,"image",2000); priority=data.get("priority","normal")
    if icon not in ICONS:icon="website"
    if badge not in BADGES:raise ValueError("Badge invalide")
    if priority not in {"normal","high"}:raise ValueError("Priorité invalide")
    if image and not (image.startswith("/uploads/") or image.startswith("/assets/") or valid_url(image)):raise ValueError("Image invalide")
    start,end=instant(data.get("start_at")),instant(data.get("end_at"))
    if start and end and end<=start:raise ValueError("La fin doit suivre le début")
    return {**({"calendar_timed":data["calendar_timed"]} if "calendar_timed" in data else {}),"type":kind,"internal_name":required(data,"internal_name"),"title":required(data,"title"),"description":optional(data,"description"),"url":url,"icon":icon,"image":image,"badge":badge,"cta":optional(data,"cta",80),**({"promo_code":optional(data,"promo_code",80)} if "promo_code" in data else {}),"priority":priority,"active":1 if data.get("active",True) else 0,"draft":1 if data.get("draft",False) else 0,"start_at":start.isoformat().replace("+00:00","Z") if start else None,"end_at":end.isoformat().replace("+00:00","Z") if end else None}
def promotion_rows(db,exclude_id=None):
    query="SELECT * FROM content_blocks WHERE type IN ('promo','featured') AND active=1 AND draft=0 AND archived=0"
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
    all_rows=list(db.execute("SELECT * FROM content_blocks WHERE type IN ('promo','featured') AND archived=0"))
    active=sum(status_of(row,now)=="Actif" for row in all_rows);programmed=sum(status_of(row,now)=="Programmé" for row in all_rows)
    if item["type"] not in {"promo","featured"} or not item["active"] or item["draft"]:
        return {"allowed":True,"maximum":0,"overlaps":[],"segments":[],"next_start":None,"active":active,"programmed":programmed}
    start,end=promotion_interval(item,now)
    maximum,overlap,segments=concurrency(rows,start,end)
    duration=None if end==float("inf") else end-start
    next_start=None
    if maximum>3:
        candidates=sorted({start}|{re for row in rows for _,re in [promotion_interval(row,now)] if re!=float("inf") and re>=start})
        for candidate in candidates:
            candidate_end=float("inf") if duration is None else candidate+duration
            if concurrency(rows,candidate,candidate_end)[0]<=3:
                next_start=datetime.fromtimestamp(candidate,timezone.utc).isoformat().replace("+00:00","Z");break
    return {"allowed":maximum<=3,"maximum":maximum,"overlaps":[promotion_snapshot(row,now) for row,_,_ in overlap],"segments":segments,"next_start":next_start,"active":active,"programmed":programmed}
def ensure_promotion_capacity(item,exclude_id=None,db=None):
    check=promotion_check(item,exclude_id,db)
    if not check["allowed"]:raise ValueError("Limite de 3 promotions simultanées dépassée")
    return check
def button_data(data):
    icon=data.get("icon","website");url=required(data,"url",2000)
    if icon not in ICONS:raise ValueError("Icône invalide")
    if url.startswith("#"):
        if not re.fullmatch(r"#[A-Za-z][\w:-]*",url):raise ValueError("Ancre invalide")
    elif not valid_url(url):raise ValueError("URL invalide")
    return {"icon":icon,"label":required(data,"label",100),"url":url,"active":1 if data.get("active",True) else 0}
def valid_metric(key):
    if key=="latest-video":return True
    table,prefix=("content_blocks","block:") if key.startswith("block:") else (("top_buttons","button:") if key.startswith("button:") else (None,None))
    if table:
        with connection() as db:return db.execute(f"SELECT 1 FROM {table} WHERE id=?",(key.removeprefix(prefix),)).fetchone() is not None
    return (key.startswith("social:") or key.startswith("link:")) and len(key)<=2048

def save_content(db,item,item_id=None):
    ensure_promotion_capacity(item,item_id,db)
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

BACKUP_TABLES=('content_blocks','top_buttons','settings','counts','story_links','footer_quotes')
BACKUP_LIMIT=64*1024*1024
UPLOAD_NAME=re.compile(r'[a-f0-9-]{36}\.(jpg|png|webp|gif)')

def export_backup():
    with DATA_LOCK,connection() as db:
        tables={table:[dict(row) for row in db.execute('SELECT * FROM '+table)] for table in BACKUP_TABLES}
        references={r['image'] for r in tables['content_blocks']}
        references.update(r['value'] for r in tables['settings'] if r['key'] in {'profile.avatar','profile.logo'})
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
        result={'format':'links-backup','version':3,'created_at':now_iso(),'tables':tables,'images':images,'assets':assets}
        encoded=json.dumps(result,ensure_ascii=False).encode()
        if len(encoded)>BACKUP_LIMIT:raise ValueError('Sauvegarde supérieure à 64 Mo : sauvegarder le volume serveur')
        return encoded

def restore_backup(data):
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
    if set(tables)!=set(BACKUP_TABLES):raise ValueError('Sauvegarde incomplète')
    assets=data.get('assets',{})
    if not isinstance(assets,dict):raise ValueError('Assets invalides')
    asset_bytes={}
    for name,encoded in assets.items():
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9._-]+\.(webp|jpg|jpeg|png|gif)',name) or not isinstance(encoded,str):raise ValueError('Asset invalide')
        raw=base64.b64decode(encoded,validate=True)
        if not 0<len(raw)<=4*1024*1024:raise ValueError('Asset trop volumineux')
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
        new_name=str(uuid.uuid4())+Path(name).suffix
        mapping['/uploads/'+name]='/uploads/'+new_name;decoded[new_name]=raw
    try:
        with DATA_LOCK,connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for table in BACKUP_TABLES:
                rows=tables[table]
                if not isinstance(rows,list) or len(rows)>500000:raise ValueError('Table invalide : '+table)
                schema=list(db.execute('PRAGMA table_info('+table+')'));columns=[c['name'] for c in schema]
                primary=[c['name'] for c in schema if c['pk']]
                keys=[tuple(row.get(k) for k in primary) for row in rows if isinstance(row,dict)]
                if len(keys)!=len(set(keys)):raise ValueError('Identifiants en double : '+table)
                for row in rows:
                    if table=='content_blocks' and isinstance(row,dict) and 'promo_code' not in row:row['promo_code']=''
                    if not isinstance(row,dict) or set(row)!=set(columns):raise ValueError('Structure incompatible : '+table)
                    for column in schema:
                        value=row[column['name']]
                        if value is None:
                            if column['notnull'] or column['pk']:raise ValueError('Valeur obligatoire absente')
                        elif column['type']=='INTEGER':
                            if type(value) is not int or not 0<=value<2**53:raise ValueError('Compteur ou position invalide')
                        elif not isinstance(value,str) or len(value)>16384:raise ValueError('Texte invalide')
                    if table=='content_blocks':
                        block_data(row)
                        if any(row[k] not in (0,1) for k in ['active','draft','archived']):raise ValueError('État invalide')
                    elif table=='top_buttons':
                        button_data({**row,'icon':'mail' if row['icon']=='email' else row['icon']})
                    elif table=='counts':
                        date.fromisoformat(row['day'])
                        if row['kind'] not in {'view','click','impression','story','promo_code_copy'} or row['total']<1:raise ValueError('Statistique invalide')
                        if row['kind']=='promo_code_copy':
                            snapshot=json.loads(row['link'])
                            if not isinstance(snapshot,dict) or set(snapshot)!={'id','name','code','timestamp'} or any(not isinstance(v,str) for v in snapshot.values()) or not snapshot['code'] or len(snapshot['code'])>80:raise ValueError('Copie de code invalide')
                            instant(snapshot['timestamp'])
                        if row['kind']=='story' and (row['source']!='instagram-story' or not re.fullmatch(r'story:st_[A-Za-z0-9_-]{16}:\d{2}',row['link']) or int(row['link'][-2:])>23):raise ValueError('Statistique Story invalide')
                    elif table=='story_links':
                        if not STORY_TOKEN.fullmatch(row['token']) or row['deleted'] not in (0,1) or not row['name'] or not row['promotion_id']:raise ValueError('Lien Story invalide')
                        instant(row['created_at'])
                    elif table=='footer_quotes':
                        if not row['text'].strip() or len(row['text'])>1000 or row['active'] not in (0,1):raise ValueError('Citation invalide')
                        instant(row['created_at'])
                    elif row['key'] not in instance.CONFIG_KEYS:raise ValueError('Réglage inconnu')
            if len(tables["footer_quotes"])>300:raise ValueError("Maximum 300 citations")
            incoming_settings={r["key"]:r["value"] for r in tables["settings"]}
            validate_settings(incoming_settings)
            for row in tables["settings"]:
                if row["key"]=="app.version":checked_version(row["value"])
            setting_keys={row["key"] for row in tables["settings"]}
            for row in db.execute("SELECT * FROM settings"):
                if row["key"] in {"auth.mode","app.setup_completed","app.config_schema_version"}:
                    tables["settings"]=[r for r in tables["settings"] if r["key"]!=row["key"]];tables["settings"].append(dict(row));continue
                if row["key"] not in setting_keys:tables["settings"].append(dict(row))
            # Codes are never reassigned, even when restoring a different backup.
            incoming={r['token']:r for r in tables['story_links']}
            restored_ids={r['id'] for r in tables['content_blocks']}
            for old in db.execute('SELECT * FROM story_links'):
                if old['token'] in incoming:
                    if incoming[old['token']]['promotion_id']!=old['promotion_id']:raise ValueError('Un identifiant Story ne peut pas changer de promotion')
                elif any(r['promotion_id']==old['promotion_id'] for r in incoming.values()):raise ValueError('Identifiants Story incompatibles avec les liens existants')
                else:tables['story_links'].append({**dict(old),'deleted':int(old['promotion_id'] not in restored_ids)})
            tokens={r['token'] for r in tables['story_links']}
            if any(r['kind']=='story' and r['link'].split(':')[1] not in tokens for r in tables['counts']):raise ValueError('Référent Story manquant')
            # Every uploaded image used by the restored content must exist in this backup.
            for row in tables['content_blocks']:
                if row['image'].startswith('/uploads/'):
                    if row['image'] not in mapping:raise ValueError('Image manquante dans la sauvegarde')
                    row['image']=mapping[row['image']]
            for row in tables['settings']:
                if row['key'] in {'profile.avatar','profile.logo'} and row['value'].startswith('/uploads/'):
                    if row['value'] not in mapping:raise ValueError('Image de profil manquante')
                    row['value']=mapping[row['value']]
            refs=[r['image'] for r in tables['content_blocks']]+[r['value'] for r in tables['settings'] if r['key'] in {'profile.logo','profile.avatar'}]
            for ref in refs:
                if ref.startswith('/assets/') and not (STATIC/ref[1:]).is_file() and not (DATA_DIR/ref[1:]).is_file() and ref[8:] not in asset_bytes:raise ValueError('Asset référencé manquant')
            for table in BACKUP_TABLES:
                db.execute('DELETE FROM '+table)
                columns=[c['name'] for c in db.execute('PRAGMA table_info('+table+')')]
                db.executemany('INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',[[row[c] for c in columns] for row in tables[table]])
            db.execute("INSERT OR REPLACE INTO settings VALUES('content.initialized','1')")
            for row in db.execute("SELECT * FROM content_blocks WHERE archived=0 AND active=1 AND draft=0 AND type IN ('promo','featured')"):
                ensure_promotion_capacity(dict(row),row['id'],db)
            # New filenames ensure that a failed restore cannot overwrite current images.
            for name,raw in decoded.items():
                target=UPLOADS/name;written.append(target);target.write_bytes(raw)
            (DATA_DIR/'assets').mkdir(exist_ok=True)
            for name,raw in asset_bytes.items():
                target=DATA_DIR/'assets'/name
                if not target.exists():written.append(target);target.write_bytes(raw)
            db.execute('DELETE FROM admin_sessions')
        with connection() as db:sync_configuration(db)
        return {'blocks':len(tables['content_blocks']),'buttons':len(tables['top_buttons']),'images':len(images)}
    except Exception:
        for path in written:path.unlink(missing_ok=True)
        raise


def validate_settings(values):
    if 'admin.calendar_timed' in values:
        ids=json.loads(values['admin.calendar_timed'])
        if not isinstance(ids,list) or any(not isinstance(x,str) or not re.fullmatch(r'[a-f0-9-]{36}',x) for x in ids):raise ValueError('Modes horaires invalides')
    if 'admin.content_order' in values:
        order=json.loads(values['admin.content_order'])
        if not isinstance(order,list) or len(order)!=3 or any(not isinstance(x,str) for x in order) or set(order)!={'classic','video','highlight'}:raise ValueError('Ordre des sections invalide')
    if 'site.url' in values:values['site.url']=instance.site_url(values['site.url'],allow_empty=True)
    if 'app.timezone' in values:instance.timezone_name(values['app.timezone'])
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

class Handler(BaseHTTPRequestHandler):
    def handle_one_request(self):
        self.response_status=0
        super().handle_one_request()
        if self.server.admin and getattr(self,'command','') in {'POST','PUT','DELETE'} and 200<=self.response_status<300:
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
        if path in {'/brand.svg','/brand-light.svg','/mark.svg'}:return False
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
                        if not 0<len(logo_raw)<=4*1024*1024:raise ValueError('Logo vide ou supérieur à 4 Mo.')
                        name=str(uuid.uuid4())+IMAGE_TYPES[logo['type']];values['profile.logo']='/uploads/'+name
                    # No writes happen until all fields and credentials validate.
                    instance.account(db,data.get('username'),data.get('password'))
                    for key,value in values.items():instance.put(db,key,value)
                    save_content(db,first)
                    instance.put(db,'auth.mode','local');instance.put(db,'app.setup_completed','true');instance.put(db,'content.initialized','1')
                    db.execute("DELETE FROM auth_state WHERE key='bootstrap_hash'")
                    token=instance.new_session(db)
                    if logo_raw is not None:
                        self.setup_upload=UPLOADS/name;self.setup_upload.write_bytes(logo_raw)
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
        self.send_response(status);self.send_header("Content-Type",mime);self.send_header("Content-Length",str(len(body)));self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");self.send_header("Content-Security-Policy","default-src 'self';script-src 'self';style-src 'self';img-src 'self' data:;object-src 'none';frame-ancestors 'none';base-uri 'none'");self.end_headers();self.wfile.write(body)
    def json(self,status,data):self.send(status,json.dumps(data,ensure_ascii=False).encode())
    def body(self,limit=8*1024*1024):
        size=int(self.headers.get("Content-Length","0"))
        if not 0<size<=limit:raise ValueError("Corps invalide")
        data=json.loads(self.rfile.read(size))
        if not isinstance(data,dict):raise ValueError("Objet attendu")
        return data
    def file(self,path,mime=None):
        try:data=path.read_bytes()
        except OSError:return self.send(404)
        self.send(200,data,mime or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
    def do_GET(self):
        if self.server.admin and self.auth_get():return
        url=urlsplit(self.path)
        if self.server.admin and url.path in {"/brand.svg","/brand-light.svg","/mark.svg"}:return self.file(ADMIN/url.path[1:],"image/svg+xml")
        if url.path.startswith('/go/'):
            return self.redirect_story(url.path.removeprefix('/go/'))
        if url.path=="/latest-video.json":
            try:return self.json(200,latest_video())
            except (OSError,ValueError):return self.json(502,{"error":"Vidéo momentanément indisponible"})
        if url.path=="/healthz":
            try:
                with connection() as db:db.execute("SELECT total FROM counts LIMIT 1").fetchone()
                return self.send(200,b"ok","text/plain")
            except sqlite3.Error:return self.send(503)
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
            if url.path=="/api/youtube":return self.json(200,youtube_status())
            if url.path=="/api/quotes":return self.json(200,{"items":quote_list()})
            if url.path=="/api/backup":return self.send(200,export_backup())
            if url.path=="/api/stats":
                q=parse_qs(url.query);today=datetime.now(PARIS).date();return self.json(200,report(q.get("start",[(today-timedelta(days=29)).isoformat()])[0],q.get("end",[today.isoformat()])[0],q.get("source",[""])[0]))
            if url.path=="/api/content":return self.json(200,{"items":content_list(parse_qs(url.query).get("archived",["0"])[0]=="1")})
            if url.path=="/api/buttons":return self.json(200,{"items":button_list()})
            if url.path=="/api/settings":
                with connection() as db:return self.json(200,profile(db))
            if url.path=="/api/public-config":return self.json(200,public_config())
        except (ValueError,TypeError) as exc:return self.json(400,{"error":str(exc) or "Paramètres invalides"})
        if url.path=="/preview/cards.js":return self.file(STATIC/"cards.js","application/javascript")
        if url.path=="/preview/icons.css":return self.file(STATIC/"icons.css","text/css")
        if url.path=="/preview/style.css":return self.file(ROOT/"site"/"style.css" if (ROOT/"site"/"style.css").exists() else Path("/usr/share/nginx/html/style.css"),"text/css")
        if url.path=="/preview/preview.css":return self.file(ADMIN/"promo-preview.css","text/css")
        files={"/":("index.html","text/html;charset=utf-8"),"/app.js":("app.js","application/javascript"),"/dates.js":("dates.js","application/javascript"),"/calendar.js":("calendar.js","application/javascript"),"/style.css":("style.css","text/css")}
        return self.file(ADMIN/files[url.path][0],files[url.path][1]) if url.path in files else self.send(404)
    def do_POST(self):
        if self.server.admin and self.auth_post():return
        path=urlsplit(self.path).path
        if not self.server.admin:
            if path!="/metrics":return self.send(404)
            if not analytics_enabled():return self.send(204)
            if self.headers.get("Origin")!=ORIGIN:return self.send(403)
            if any(x in self.headers.get("User-Agent","").lower() for x in ["bot","spider","crawler","headless"]):return self.send(204)
            try:
                data=self.body(2048);kind,key=data.get("kind"),data.get("link","")
                if kind=="promo_code_copy":record_promo_copy(data);return self.send(204)
                if kind not in {"view","click","impression"} or not isinstance(key,str) or (kind in {"click","impression"} and not valid_metric(key)):raise ValueError()
                record(kind,source_of(data),key if kind in {"click","impression"} else "");return self.send(204)
            except (ValueError,TypeError,json.JSONDecodeError):return self.send(400)
            except sqlite3.Error:return self.send(503)
        try:
            data=self.body(BACKUP_LIMIT if path=="/api/restore" else 8*1024*1024)
            if path=="/api/youtube/test":return self.json(200,youtube_test(data))
            if path=="/api/youtube":return self.json(200,save_youtube(data))
            if path=="/api/quotes/analyze":return self.json(200,add_quotes(data,preview=True))
            if path=="/api/quotes":return self.json(200,add_quotes(data))
            if path=="/api/restore":return self.json(200,restore_backup(data))
            if path=="/api/promotions/replace":return self.replace_promotion(data)
            if path=="/api/content":return self.create_content(data)
            if path=="/api/promotions/check":
                item=block_data(data);return self.json(200,promotion_check(item,data.get("id") or None))
            if path=="/api/content/reorder":return self.reorder("content_blocks",data)
            match=re.fullmatch(r"/api/content/([\w-]+)/story-link",path)
            if match:return self.json(200,story_link(match.group(1)))
            match=re.fullmatch(r"/api/content/([\w-]+)/(duplicate|archive|restore)",path)
            if match:return self.content_action(match.group(1),match.group(2))
            if path=="/api/buttons":return self.create_button(data)
            if path=="/api/buttons/reorder":return self.reorder("top_buttons",data)
            if path=="/api/upload":return self.upload(data)
            if path=="/api/app-version":
                value=checked_version(data.get("app_version"))
                with connection() as db:db.execute("INSERT INTO settings VALUES('app.version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(value,))
                return self.json(200,{"app_version":value})
            if path=="/api/settings":return self.save_settings(data)
            return self.send(404)
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
            match=re.fullmatch(r"/api/content/([\w-]+)",path)
            if match:return self.update_content(match.group(1),data)
            match=re.fullmatch(r"/api/buttons/([\w-]+)",path)
            if match:return self.update_button(match.group(1),data)
            return self.send(404)
        except (ValueError,TypeError,json.JSONDecodeError) as exc:return self.json(400,{"error":str(exc) or "Requête invalide"})
    def do_DELETE(self):
        if self.server.admin and not self.authorized(mutation=True):return
        if not self.server.admin:return self.send(404)
        path=urlsplit(self.path).path
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
            prefix="block:" if table=="content_blocks" else "button:"
            if table=='content_blocks':
                db.execute('UPDATE story_links SET name=COALESCE((SELECT internal_name FROM content_blocks WHERE id=?),name),deleted=1 WHERE promotion_id=?',(match.group(1),match.group(1)))
            changed=db.execute(f"DELETE FROM {table} WHERE id=?",(match.group(1),)).rowcount
            if changed:db.execute("DELETE FROM counts WHERE kind IN ('click','impression') AND link=?",(prefix+match.group(1),))
        return self.send(204) if changed else self.send(404)
    def do_HEAD(self):
        path=urlsplit(self.path).path
        return self.redirect_story(path.removeprefix('/go/'),count=False) if path.startswith('/go/') else self.send(404)
    def redirect_story(self,token,count=True):
        if not STORY_TOKEN.fullmatch(token):return self.send(404)
        try:
            with connection() as db:
                db.execute('BEGIN IMMEDIATE')
                item=db.execute('''SELECT b.url,b.internal_name,s.deleted FROM story_links s
                  LEFT JOIN content_blocks b ON b.id=s.promotion_id WHERE s.token=?''',(token,)).fetchone()
                if not item:return self.send(404)
                if item['deleted'] or not item['url']:return self.send(410)
                if not story_url_valid(item['url']):return self.send(410)
                agent=self.headers.get('User-Agent','').lower()
                if count and instance.get(db,"analytics.enabled")=="true" and not any(x in agent for x in ['bot','spider','crawler','headless','facebookexternalhit','meta-externalagent','preview']):
                    now=datetime.now(PARIS)
                    increment(db,'story','instagram-story','story:'+token+':'+now.strftime('%H'),now.date().isoformat())
                target=story_destination(item['url'])
            self.send_response(302);self.send_header('Location',target);self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Length','0');self.end_headers()
        except (sqlite3.Error,OSError):return self.send(503)
    def create_content(self,data):
        item=block_data(data)
        with connection() as db:
            db.execute("BEGIN IMMEDIATE")
            item_id=save_content(db,item)
        return self.json(201,{"id":item_id})
    def update_content(self,item_id,data):
        item=block_data(data)
        with connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM content_blocks WHERE id=?",(item_id,)).fetchone():return self.send(404)
            save_content(db,item,item_id)
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
            item_id=save_content(db,item,item_id)
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
                timed=json.loads(instance.get(db,'admin.calendar_timed') or '[]')
                if item_id in timed:instance.put(db,'admin.calendar_timed',json.dumps(timed+[new_id]))
                return self.json(201,{"id":new_id})
            if action=="restore":ensure_promotion_capacity(dict(row),item_id,db)
            db.execute("UPDATE content_blocks SET archived=?,updated_at=? WHERE id=?",(1 if action=="archive" else 0,now_iso(),item_id))
        return self.send(204)
    def reorder(self,table,data):
        ids=data.get("ids")
        if not isinstance(ids,list) or not ids or len(ids)>500 or len(set(ids))!=len(ids):raise ValueError("Ordre invalide")
        with connection() as db:
            for pos,item_id in enumerate(ids):
                if not db.execute(f"SELECT 1 FROM {table} WHERE id=?",(item_id,)).fetchone():raise ValueError("Élément inconnu")
                db.execute(f"UPDATE {table} SET position=?,updated_at=? WHERE id=?",(pos,now_iso(),item_id))
        return self.send(204)
    def create_button(self,data):
        item=button_data(data);item_id=str(uuid.uuid4());stamp=now_iso()
        with connection() as db:pos=db.execute("SELECT COALESCE(MAX(position),-1)+1 FROM top_buttons").fetchone()[0];db.execute("INSERT INTO top_buttons VALUES(?,?,?,?,?,?,?,?)",(item_id,item["icon"],item["label"],item["url"],pos,item["active"],stamp,stamp))
        return self.json(201,{"id":item_id})
    def update_button(self,item_id,data):
        item=button_data(data)
        with connection() as db:changed=db.execute("UPDATE top_buttons SET icon=?,label=?,url=?,active=?,updated_at=? WHERE id=?",(item["icon"],item["label"],item["url"],item["active"],now_iso(),item_id)).rowcount
        return self.send(204) if changed else self.send(404)
    def upload(self,data):
        mime=data.get("type","");encoded=data.get("data","")
        if mime not in IMAGE_TYPES or not isinstance(encoded,str):raise ValueError("Format d’image non pris en charge")
        raw=base64.b64decode(encoded.split(",",1)[-1],validate=True)
        if not raw or len(raw)>4*1024*1024:raise ValueError("Image vide ou supérieure à 4 Mo")
        name=str(uuid.uuid4())+IMAGE_TYPES[mime];(UPLOADS/name).write_bytes(raw);return self.json(201,{"url":"/uploads/"+name})
    def save_settings(self,data):
        values=configuration_input(data)
        with connection() as db:
            for key,value in values.items():instance.put(db,key,value)
            sync_configuration(db)
        return self.send(204)


def serve(port,admin,host):
    server=ThreadingHTTPServer((host,port),Handler);server.admin=admin;return server
if __name__=="__main__":
    init();write_public_fallback();public=serve(3003,False,"127.0.0.1");threading.Thread(target=public.serve_forever,daemon=True).start();serve(8081,True,"0.0.0.0").serve_forever()
