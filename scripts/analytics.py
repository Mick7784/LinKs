"""Small SQLite content manager and aggregate analytics service."""
import base64, binascii, json, mimetypes, os, re, secrets, sqlite3, threading, uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
if not (ROOT/"links.json").exists(): ROOT=ROOT.parent
DB=os.environ.get("ANALYTICS_DB","/data/analytics.db")
ORIGIN=os.environ.get("ANALYTICS_ORIGIN","https://links.domotik-studio.fr").rstrip("/")
ADMIN=ROOT/"admin"; UPLOADS=Path(os.environ.get("UPLOAD_DIR","/data/uploads"))
CONFIG=json.loads((ROOT/"links.json").read_text(encoding="utf-8"))
DATA_LOCK=threading.RLock()
PARIS=ZoneInfo("Europe/Paris")
TYPES={"classic","promo","featured"}; ICONS={"youtube","instagram","tiktok","discord","mail","website","cart","home"}
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
    Path(DB).parent.mkdir(parents=True,exist_ok=True); UPLOADS.mkdir(parents=True,exist_ok=True)
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
        db.execute("""CREATE TABLE IF NOT EXISTS top_buttons(
          id TEXT PRIMARY KEY,icon TEXT NOT NULL,label TEXT NOT NULL,url TEXT NOT NULL,position INTEGER NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
        db.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        db.execute("""CREATE TABLE IF NOT EXISTS story_links(
          token TEXT PRIMARY KEY,promotion_id TEXT NOT NULL UNIQUE,name TEXT NOT NULL,
          created_at TEXT NOT NULL,deleted INTEGER NOT NULL DEFAULT 0)""")
        seed(db)

def seed(db):
    if db.execute("SELECT 1 FROM settings WHERE key='content.initialized'").fetchone():return
    stamp=now_iso()
    if db.execute("SELECT COUNT(*) FROM content_blocks").fetchone()[0]==0:
        for i,item in enumerate(CONFIG.get("links",[])):
            db.execute("""INSERT INTO content_blocks(id,type,internal_name,title,description,url,icon,image,badge,cta,position,active,draft,start_at,end_at,archived,created_at,updated_at,priority)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
              f"legacy-link-{i}","featured" if item.get("featured") else "classic",item.get("title",f"Lien {i+1}"),
              item.get("title",""),item.get("description",""),item.get("url",""),item.get("icon","website"),
              item.get("image",""),"","Découvrir",i,1,0,None,legacy_expiry(item.get("expiresAt")),0,stamp,stamp,"normal"))
    if db.execute("SELECT COUNT(*) FROM top_buttons").fetchone()[0]==0:
        for i,item in enumerate(CONFIG.get("socials",[])):
            db.execute("INSERT INTO top_buttons VALUES(?,?,?,?,?,?,?,?)",(f"legacy-button-{i}",item.get("platform","website"),item.get("label",item.get("platform","Lien")),item.get("url",""),i,1,stamp,stamp))
    profile=CONFIG.get("profile",{})
    for key,value in {"name":profile.get("name","DomotiK Studio"),"tagline":profile.get("tagline",""),"description":profile.get("description",""),"avatar":profile.get("avatar","/assets/portrait.webp"),"logo":profile.get("logo","/assets/logo.webp")}.items():
        db.execute("INSERT OR IGNORE INTO settings VALUES(?,?)",("profile."+key,value))

    db.execute("INSERT OR REPLACE INTO settings VALUES('content.initialized','1')")

def record(kind,source,link,day=None):
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
    known={"yt","ig","youtube","instagram","facebook","tiktok","discord","google","newsletter","domotik-studio","domotik-studio.fr"}
    if source:return {"yt":"youtube","ig":"instagram","domotik-studio":"domotik-studio.fr"}.get(source,source) if source in known else "autre-campagne"
    ref=data.get("referrer","")
    if not isinstance(ref,str):raise ValueError()
    host=(urlsplit(ref).hostname or "").lower()
    if host==urlsplit(ORIGIN).hostname:return "direct-inconnu"
    for domain,name in [("youtube.com","youtube"),("youtu.be","youtube"),("instagram.com","instagram"),("facebook.com","facebook"),("tiktok.com","tiktok"),("discord.com","discord"),("google.com","google"),("google.fr","google"),("domotik-studio.fr","domotik-studio.fr")]:
        if host==domain or host.endswith("."+domain):return name
    return "autre-site" if host else "direct-inconnu"
def metric_aliases(db):
    # Only seeded items have a known predecessor. Never merge distinct blocks
    # merely because they share a display title; keep stored history untouched.
    candidates={}
    for config_key,table,prefix,id_prefix,label_key,label_prefix in [
        ("links","content_blocks","block:","legacy-link-","title",""),
        ("socials","top_buttons","button:","legacy-button-","label","Réseau · ")]:
        existing={r["id"] for r in db.execute(f"SELECT id FROM {table}")}
        for index,item in enumerate(CONFIG.get(config_key,[])):
            item_id=id_prefix+str(index)
            label=item.get(label_key) or item.get("platform","")
            if label:
                candidates.setdefault(label_prefix+label,set()).add(prefix+item_id)
        for label,keys in list(candidates.items()):
            # Missing or ambiguous predecessors must remain separate.
            if len(keys)==1:
                key=next(iter(keys))
                if key.startswith(prefix) and key.removeprefix(prefix) not in existing:
                    candidates[label]=set()
    return {label:next(iter(keys)) for label,keys in candidates.items() if len(keys)==1}

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
    return {"rows":rows,"stories":stories,"timezone":"Europe/Paris"}

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
    values={r["key"]:r["value"] for r in db.execute("SELECT key,value FROM settings")}
    return {k:values.get("profile."+k,"") for k in ["name","tagline","description","avatar","logo"]}
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
        clicks=totals(db); return [serialize(r,clicks) for r in db.execute("SELECT * FROM content_blocks WHERE archived=? ORDER BY CASE WHEN type IN ('promo','featured') THEN 0 ELSE 1 END,position,created_at",(1 if archived else 0,))]
def button_list():
    with connection() as db:
        clicks=totals(db); result=[]
        for row in db.execute("SELECT * FROM top_buttons ORDER BY position,created_at"):
            item=dict(row);item["active"]=bool(item["active"]);item["clicks"]=clicks.get(("click","button:"+item["id"]),0);result.append(item)
        return result
def public_config():
    with connection() as db:
        blocks=[serialize(r) for r in db.execute("SELECT * FROM content_blocks WHERE archived=0 ORDER BY CASE WHEN type IN ('promo','featured') THEN 0 ELSE 1 END,CASE WHEN priority='high' THEN 0 ELSE 1 END,position,created_at") if status_of(r)=="Actif"]
        buttons=[dict(r) for r in db.execute("SELECT * FROM top_buttons WHERE active=1 ORDER BY position,created_at")]
        result={"profile":profile(db),"socials":[{"id":x["id"],"platform":x["icon"],"label":x["label"],"url":x["url"],"metricKey":"button:"+x["id"]} for x in buttons],
                "links":[{"id":x["id"],"type":x["type"],"title":x["title"],"description":x["description"],"url":x["url"],"icon":x["icon"],"image":x["image"],"badge":x["badge"],"cta":x["cta"],"priority":x["priority"],"metricKey":"block:"+x["id"]} for x in blocks]}
    if CONFIG.get("latestVideo"):result["latestVideo"]=CONFIG["latestVideo"]
    return result

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
    return {"type":kind,"internal_name":required(data,"internal_name"),"title":required(data,"title"),"description":optional(data,"description"),"url":url,"icon":icon,"image":image,"badge":badge,"cta":optional(data,"cta",80),"priority":priority,"active":1 if data.get("active",True) else 0,"draft":1 if data.get("draft",False) else 0,"start_at":start.isoformat().replace("+00:00","Z") if start else None,"end_at":end.isoformat().replace("+00:00","Z") if end else None}
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
    return item_id

BACKUP_TABLES=('content_blocks','top_buttons','settings','counts','story_links')
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
        result={'format':'domotik-links-backup','version':2,'created_at':now_iso(),'tables':tables,'images':images}
        encoded=json.dumps(result,ensure_ascii=False).encode()
        if len(encoded)>BACKUP_LIMIT:raise ValueError('Sauvegarde supérieure à 64 Mo : sauvegarder le volume serveur')
        return encoded

def restore_backup(data):
    if data.get('format')!='domotik-links-backup' or data.get('version') not in {1,2}:raise ValueError('Ce fichier n’est pas une sauvegarde Links compatible')
    tables=data.get('tables');images=data.get('images')
    if data.get('version')==1 and isinstance(tables,dict) and set(tables)==set(BACKUP_TABLES)-{'story_links'}:
        # An old backup predates Stories: retain the new history and reserved codes.
        with connection() as db:
            tables={**tables,'story_links':[dict(r) for r in db.execute('SELECT * FROM story_links')]}
            if isinstance(tables.get('counts'),list):tables['counts']=tables['counts']+[dict(r) for r in db.execute("SELECT * FROM counts WHERE kind='story'")]
    if not isinstance(tables,dict) or set(tables)!=set(BACKUP_TABLES) or not isinstance(images,dict):raise ValueError('Sauvegarde incomplète')
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
                for row in rows:
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
                        if row['kind'] not in {'view','click','impression','story'} or row['total']<1:raise ValueError('Statistique invalide')
                        if row['kind']=='story' and (row['source']!='instagram-story' or not re.fullmatch(r'story:st_[A-Za-z0-9_-]{16}:\d{2}',row['link']) or int(row['link'][-2:])>23):raise ValueError('Statistique Story invalide')
                    elif table=='story_links':
                        if not STORY_TOKEN.fullmatch(row['token']) or row['deleted'] not in (0,1) or not row['name'] or not row['promotion_id']:raise ValueError('Lien Story invalide')
                        instant(row['created_at'])
                    elif row['key'] not in {'content.initialized','profile.name','profile.tagline','profile.description','profile.avatar','profile.logo'}:raise ValueError('Réglage inconnu')
            # Codes are never reassigned, even when restoring a different backup.
            incoming={r['token']:r for r in tables['story_links']}
            for old in db.execute('SELECT * FROM story_links'):
                if old['token'] in incoming:
                    if incoming[old['token']]['promotion_id']!=old['promotion_id']:raise ValueError('Un identifiant Story ne peut pas changer de promotion')
                elif any(r['promotion_id']==old['promotion_id'] for r in incoming.values()):raise ValueError('Identifiants Story incompatibles avec les liens existants')
                else:tables['story_links'].append({**dict(old),'deleted':1})
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
        return {'blocks':len(tables['content_blocks']),'buttons':len(tables['top_buttons']),'images':len(images)}
    except Exception:
        for path in written:path.unlink(missing_ok=True)
        raise


class Handler(BaseHTTPRequestHandler):
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
        url=urlsplit(self.path)
        if url.path.startswith('/go/'):
            return self.redirect_story(url.path.removeprefix('/go/'))
        if url.path=="/healthz":
            try:
                with connection() as db:db.execute("SELECT total FROM counts LIMIT 1").fetchone()
                return self.send(200,b"ok","text/plain")
            except sqlite3.Error:return self.send(503)
        if url.path.startswith("/uploads/"):
            name=unquote(url.path.removeprefix("/uploads/"))
            return self.file(UPLOADS/name) if re.fullmatch(r"[a-f0-9-]{36}\.(jpg|png|webp|gif)",name) else self.send(404)
        if not self.server.admin:return self.json(200,public_config()) if url.path=="/api/public-config" else self.send(404)
        try:
            if url.path=="/api/backup":return self.send(200,export_backup())
            if url.path=="/api/stats":
                q=parse_qs(url.query);today=datetime.now(PARIS).date();return self.json(200,report(q.get("start",[(today-timedelta(days=29)).isoformat()])[0],q.get("end",[today.isoformat()])[0],q.get("source",[""])[0]))
            if url.path=="/api/content":return self.json(200,{"items":content_list(parse_qs(url.query).get("archived",["0"])[0]=="1")})
            if url.path=="/api/buttons":return self.json(200,{"items":button_list()})
            if url.path=="/api/settings":
                with connection() as db:return self.json(200,profile(db))
            if url.path=="/api/public-config":return self.json(200,public_config())
        except (ValueError,TypeError) as exc:return self.json(400,{"error":str(exc) or "Paramètres invalides"})
        files={"/":("index.html","text/html;charset=utf-8"),"/app.js":("app.js","application/javascript"),"/style.css":("style.css","text/css")}
        return self.file(ADMIN/files[url.path][0],files[url.path][1]) if url.path in files else self.send(404)
    def do_POST(self):
        path=urlsplit(self.path).path
        if not self.server.admin:
            if path!="/metrics":return self.send(404)
            if self.headers.get("Origin")!=ORIGIN:return self.send(403)
            if any(x in self.headers.get("User-Agent","").lower() for x in ["bot","spider","crawler","headless"]):return self.send(204)
            try:
                data=self.body(2048);kind,key=data.get("kind"),data.get("link","")
                if kind not in {"view","click","impression"} or not isinstance(key,str) or (kind in {"click","impression"} and not valid_metric(key)):raise ValueError()
                record(kind,source_of(data),key if kind in {"click","impression"} else "");return self.send(204)
            except (ValueError,TypeError,json.JSONDecodeError):return self.send(400)
            except sqlite3.Error:return self.send(503)
        try:
            data=self.body(BACKUP_LIMIT if path=="/api/restore" else 8*1024*1024)
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
            if path=="/api/settings":return self.save_settings(data)
            return self.send(404)
        except (ValueError,TypeError,json.JSONDecodeError,binascii.Error,sqlite3.IntegrityError) as exc:return self.json(400,{"error":str(exc) or "Requête invalide"})
        except (OSError,sqlite3.OperationalError):return self.json(503,{"error":"Stockage indisponible. Les données n’ont pas été remplacées."})
    def do_PUT(self):
        if not self.server.admin:return self.send(404)
        try:
            data=self.body();path=urlsplit(self.path).path
            match=re.fullmatch(r"/api/content/([\w-]+)",path)
            if match:return self.update_content(match.group(1),data)
            match=re.fullmatch(r"/api/buttons/([\w-]+)",path)
            if match:return self.update_button(match.group(1),data)
            return self.send(404)
        except (ValueError,TypeError,json.JSONDecodeError) as exc:return self.json(400,{"error":str(exc) or "Requête invalide"})
    def do_DELETE(self):
        if not self.server.admin:return self.send(404)
        path=urlsplit(self.path).path;match=re.fullmatch(r"/api/content/([\w-]+)",path);table="content_blocks"
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
                if count and not any(x in agent for x in ['bot','spider','crawler','headless','facebookexternalhit','meta-externalagent','preview']):
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
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(new_id,row["type"],row["internal_name"]+" (copie)",row["title"],row["description"],row["url"],row["icon"],row["image"],row["badge"],row["cta"],pos,0,1,row["start_at"],row["end_at"],0,stamp,stamp,row["priority"]));return self.json(201,{"id":new_id})
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
        values={"name":required(data,"name",120),"tagline":optional(data,"tagline",200),"description":optional(data,"description",300)}
        with connection() as db:
            for key,value in values.items():db.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",("profile."+key,value))
        return self.send(204)

def serve(port,admin,host):
    server=ThreadingHTTPServer((host,port),Handler);server.admin=admin;return server
if __name__=="__main__":
    init();public=serve(3003,False,"127.0.0.1");threading.Thread(target=public.serve_forever,daemon=True).start();serve(8081,True,"0.0.0.0").serve_forever()
