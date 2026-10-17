"""Opaque, stable public aliases for campaign and private tracked-link redirects.

A short alias points to an immutable legacy token and an optional publication
source. Keeping old tokens as the canonical identity preserves all counters,
existing published links, archived behavior and backup compatibility.
"""
import re
import secrets
import sqlite3

CODE=re.compile(r"[A-Za-z0-9_-]{9}")
LONG_TOKEN=re.compile(r"(?:st_|tk_)[A-Za-z0-9_-]{16}")
CAMPAIGN_SOURCES={"instagram","youtube","facebook","tiktok","discord","newsletter","site","mail","qr","shared-unknown"}

def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS short_aliases (
        code TEXT PRIMARY KEY,
        target_token TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL,
        revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1))
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS short_alias_lookup ON short_aliases(target_token,source,revoked)")

def campaign_source(db,value):
    """Resolve a selected source without allowing fabricated attribution."""
    if not isinstance(value,str):raise ValueError("Source de publication invalide")
    value=value.strip().lower()
    if not value:value="shared-unknown"
    if value.startswith("src_") and re.fullmatch(r"src_[a-f0-9]{32}",value):
        row=db.execute("SELECT active FROM tracking_sources WHERE id=?",(value[4:],)).fetchone()
        if not row or not row["active"]:raise ValueError("Source de publication indisponible")
        return "tracked:"+value[4:]
    if value not in CAMPAIGN_SOURCES:raise ValueError("Source de publication inconnue")
    return value

def get_or_create(db,target_token,source,origin,now):
    if not LONG_TOKEN.fullmatch(target_token):raise ValueError("Lien d'origine invalide")
    if not isinstance(source,str) or not source or len(source)>100:raise ValueError("Source de publication invalide")
    existing=db.execute("""SELECT code FROM short_aliases WHERE target_token=? AND source=? AND revoked=0
                           ORDER BY created_at,code LIMIT 1""",(target_token,source)).fetchone()
    if existing:return {"url":origin+"/"+existing["code"],"code":existing["code"]}
    for _ in range(12):
        code=secrets.token_urlsafe(9)[:9]  # 54 bits, deliberately opaque and URL-safe.
        try:
            db.execute("INSERT INTO short_aliases VALUES(?,?,?,?,0)",(code,target_token,source,now))
            return {"url":origin+"/"+code,"code":code}
        except sqlite3.IntegrityError:
            # Retry only an extremely unlikely generated-code collision.
            if db.execute("SELECT 1 FROM short_aliases WHERE code=?",(code,)).fetchone():continue
            raise
    raise ValueError("Impossible de générer un lien court")

def lookup(db,code):
    if not CODE.fullmatch(code):return None
    return db.execute("SELECT * FROM short_aliases WHERE code=?",(code,)).fetchone()

def revoke_source(db,ident,name):
    # A zero-click source can be deleted permanently, but its published
    # aliases must remain reserved and return 410, never be reassigned.
    choices=["tracked:"+ident]
    for legacy,display in (("instagram","Instagram Story"),("youtube","YouTube Post"),
                           ("facebook","Facebook"),("tiktok","TikTok"),("discord","Discord"),
                           ("instagram-story","Autre / Direct"),("shared-unknown","Autre / Direct")):
        if display==name:choices.append(legacy)
    marks=",".join("?" for _ in choices)
    db.execute("UPDATE short_aliases SET revoked=1 WHERE source IN ("+marks+")",choices)
