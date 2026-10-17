"""Private, permanent tracked links with user-managed publication sources.

Token identifiers and lifetime counters are deliberately independent of campaigns,
the 400-day analytics retention window and mutable destination/source labels.
"""
import re
import secrets
import uuid
import short_urls
from datetime import date

TOKEN = re.compile(r"tk_[A-Za-z0-9_-]{16}")
IDENT = re.compile(r"[a-f0-9]{32}")
DEFAULT_SOURCES = ("Instagram Story", "Instagram Bio", "YouTube Post",
                   "YouTube Description", "Facebook", "TikTok", "Discord",
                   "Autre / Direct")
LEGACY_SOURCES = {"instagram":"Instagram Story","youtube":"YouTube Post",
                  "facebook":"Facebook","tiktok":"TikTok","discord":"Discord",
                  "instagram-story":"Autre / Direct","shared-unknown":"Autre / Direct"}


def initialize(db):
    first_install=not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tracking_sources'").fetchone()
    db.execute("""CREATE TABLE IF NOT EXISTS tracking_sources (
        id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
        active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
        story_click_total INTEGER NOT NULL DEFAULT 0 CHECK(story_click_total >= 0),
        created_at TEXT NOT NULL)""")
    if "story_click_total" not in {row[1] for row in db.execute("PRAGMA table_info(tracking_sources)")}:
        db.execute("ALTER TABLE tracking_sources ADD COLUMN story_click_total INTEGER NOT NULL DEFAULT 0")
    db.execute("""CREATE TABLE IF NOT EXISTS tracked_links (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
        archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS tracked_tokens (
        token TEXT PRIMARY KEY, link_id TEXT NOT NULL REFERENCES tracked_links(id),
        source_id TEXT NOT NULL REFERENCES tracking_sources(id),
        click_total INTEGER NOT NULL DEFAULT 0 CHECK(click_total >= 0),
        created_at TEXT NOT NULL, UNIQUE(link_id,source_id))""")
    if first_install:
        for name in DEFAULT_SOURCES:
            codes=[key for key,label in LEGACY_SOURCES.items() if label==name]
            clicks=0
            if codes:
                slots=','.join('?' for _ in codes)
                clicks=db.execute("SELECT COALESCE(SUM(total),0) FROM counts WHERE kind='story' AND source IN ("+slots+")",codes).fetchone()[0]
            db.execute("INSERT INTO tracking_sources VALUES(?,?,1,?,datetime('now'))",(uuid.uuid4().hex,name,clicks))

def text_field(data,key,limit,required=False):
    value=data.get(key,"")
    if not isinstance(value,str):raise ValueError("Champ invalide : "+key)
    value=value.strip()
    if len(value)>limit or (required and not value):raise ValueError("Champ invalide : "+key)
    return value

def source_rows(db):
    rows=[dict(r) for r in db.execute("""SELECT s.*, (COALESCE(SUM(t.click_total),0)+s.story_click_total) AS clicks,
        COUNT(t.token) AS links FROM tracking_sources s LEFT JOIN tracked_tokens t ON t.source_id=s.id
        GROUP BY s.id ORDER BY s.created_at,s.name""")]
    return rows

def add_source(db,data,now):
    name=text_field(data,"name",100,True)
    ident=uuid.uuid4().hex
    db.execute("INSERT INTO tracking_sources VALUES(?,?,1,0,?)",(ident,name,now))
    return {"id":ident,"name":name,"active":True}

def edit_source(db,ident,data):
    current=db.execute("SELECT * FROM tracking_sources WHERE id=?",(ident,)).fetchone()
    if not current:raise ValueError("Source introuvable")
    name=text_field(data,"name",100,True)
    db.execute("UPDATE tracking_sources SET name=? WHERE id=?",(name,ident))
    return {"id":ident,"name":name}

def remove_source(db,ident):
    item=db.execute("SELECT id FROM tracking_sources WHERE id=?",(ident,)).fetchone()
    if not item:raise ValueError("Source introuvable")
    clicks=db.execute("SELECT COALESCE(SUM(click_total),0) FROM tracked_tokens WHERE source_id=?",(ident,)).fetchone()[0]
    clicks+=db.execute("SELECT story_click_total FROM tracking_sources WHERE id=?",(ident,)).fetchone()[0]
    if clicks:
        db.execute("UPDATE tracking_sources SET active=0 WHERE id=?",(ident,))
        return {"action":"archived","clicks":clicks}
    short_urls.revoke_source(db,ident,db.execute("SELECT name FROM tracking_sources WHERE id=?",(ident,)).fetchone()[0])
    db.execute("DELETE FROM tracked_tokens WHERE source_id=?",(ident,))
    db.execute("DELETE FROM tracking_sources WHERE id=?",(ident,))
    return {"action":"deleted","clicks":0}

def restore_source(db,ident):
    if not db.execute("UPDATE tracking_sources SET active=1 WHERE id=?",(ident,)).rowcount:
        raise ValueError("Source introuvable")
    return {"active":True}

def link_input(data,url_valid):
    if not isinstance(data,dict):raise ValueError("Lien invalide")
    url=text_field(data,"url",2000,True)
    if not url_valid(url):raise ValueError("Destination HTTP(S) valide requise")
    return {"name":text_field(data,"name",160,True),"url":url,
            "category":text_field(data,"category",80),"notes":text_field(data,"notes",800)}

def create_link(db,data,url_valid,now):
    fields=link_input(data,url_valid);ident=uuid.uuid4().hex
    db.execute("INSERT INTO tracked_links VALUES(?,?,?,?,?,0,1,?,?)",
               (ident,fields["name"],fields["url"],fields["category"],fields["notes"],now,now))
    return {"id":ident,**fields}

def update_link(db,ident,data,url_valid,now):
    fields=link_input(data,url_valid)
    if not db.execute("""UPDATE tracked_links SET name=?,url=?,category=?,notes=?,updated_at=?
                      WHERE id=?""",(fields["name"],fields["url"],fields["category"],fields["notes"],now,ident)).rowcount:
        raise ValueError("Lien introuvable")
    return {"id":ident,**fields}

def set_link_flag(db,ident,flag,value):
    if flag not in {"archived","enabled"}:raise ValueError("Action inconnue")
    if not db.execute("UPDATE tracked_links SET "+flag+"=? WHERE id=?",(int(value),ident)).rowcount:
        raise ValueError("Lien introuvable")
    return {flag:bool(value)}

def token_link(db,ident,source_id,origin,now):
    link=db.execute("SELECT * FROM tracked_links WHERE id=?",(ident,)).fetchone()
    source=db.execute("SELECT * FROM tracking_sources WHERE id=?",(source_id,)).fetchone()
    if not link or not source:raise ValueError("Lien ou source introuvable")
    if not source["active"]:raise ValueError("Cette source est archivée")
    if link["archived"] or not link["enabled"]:raise ValueError("Ce lien n'est pas disponible pour un nouveau partage")
    row=db.execute("SELECT token FROM tracked_tokens WHERE link_id=? AND source_id=?",(ident,source_id)).fetchone()
    if not row:
        for _ in range(8):
            token="tk_"+secrets.token_urlsafe(12)
            try:
                db.execute("INSERT INTO tracked_tokens VALUES(?,?,?,0,?)",(token,ident,source_id,now))
                break
            except Exception as exc:
                # Retry only on random-token collisions, not referential errors.
                if db.execute("SELECT token FROM tracked_tokens WHERE token=?",(token,)).fetchone():continue
                raise exc
        else:raise ValueError("Impossible de générer le lien")
    else:token=row["token"]
    alias=short_urls.get_or_create(db,token,"tracked:"+source_id,origin,now)
    return {"url":alias["url"],"token":token,"code":alias["code"],"source_id":source_id}

def find_destination(db,token):
    if not TOKEN.fullmatch(token):return None
    return db.execute("""SELECT l.url,l.enabled,t.link_id,t.source_id FROM tracked_tokens t
         JOIN tracked_links l ON l.id=t.link_id WHERE t.token=?""",(token,)).fetchone()

def count_campaign_source(db,source):
    if source.startswith("tracked:"):
        db.execute("UPDATE tracking_sources SET story_click_total=story_click_total+1 WHERE id=?",(source[8:],))
    elif source in LEGACY_SOURCES:
        db.execute("UPDATE tracking_sources SET story_click_total=story_click_total+1 WHERE name=?",(LEGACY_SOURCES[source],))

def count_click(db,token):
    db.execute("UPDATE tracked_tokens SET click_total=click_total+1 WHERE token=?",(token,))

def tracked_events(db,start,end,source=""):
    where="c.kind='tracked' AND c.day BETWEEN ? AND ?"
    params=[start,end]
    if source:where+=" AND c.source=?";params.append(source)
    return [dict(r) for r in db.execute("""SELECT c.day,c.total,c.source,c.link,
         t.link_id, t.source_id,l.name AS label,s.name AS source_name
         FROM counts c JOIN tracked_tokens t ON substr(c.link,9,length(t.token))=t.token
         JOIN tracked_links l ON l.id=t.link_id
         JOIN tracking_sources s ON s.id=t.source_id
         WHERE """+where+" ORDER BY c.day",params)]

def list_links(db,start=None,end=None):
    rows=[dict(r) for r in db.execute("SELECT * FROM tracked_links ORDER BY created_at DESC")]
    lifetime={}
    for r in db.execute("""SELECT t.link_id,t.source_id,s.name AS source_name,SUM(t.click_total) total
        FROM tracked_tokens t JOIN tracking_sources s ON s.id=t.source_id
        GROUP BY t.link_id,t.source_id"""):
        lifetime.setdefault(r["link_id"],[]).append(dict(r))
    selected={}
    if start and end:
        date.fromisoformat(start);date.fromisoformat(end)
        for r in tracked_events(db,start,end):
            key=(r["link_id"],r["source_id"])
            selected[key]=selected.get(key,0)+r["total"]
    for row in rows:
        row["sources"]=[{"id":src["source_id"],"name":src["source_name"],
                         "total":src["total"],"period":selected.get((row["id"],src["source_id"]),0)}
                        for src in lifetime.get(row["id"],[])]
        row["clicks"]=sum(r["total"] for r in row["sources"])
        row["period_clicks"]=sum(r["period"] for r in row["sources"])
    return rows
