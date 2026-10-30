"""Private, permanent tracked links with user-managed publication sources.

Token identifiers and lifetime counters are deliberately independent of campaigns,
the 400-day analytics retention window and mutable destination/source labels.
"""
import re
import secrets
import uuid
import sqlite3
from contextlib import closing
from itertools import zip_longest
from pathlib import Path
import short_urls
from urllib.parse import urlsplit
from datetime import date

TOKEN = re.compile(r"tk_[A-Za-z0-9_-]{16}")
IDENT = re.compile(r"[a-f0-9]{32}")
DEFAULT_SOURCES = ("Instagram Story", "Instagram Bio", "YouTube Post",
                   "YouTube Description", "Facebook", "TikTok", "Discord",
                   "Autre / Direct")
LEGACY_SOURCES = {"instagram":"Instagram Story","youtube":"YouTube Post",
                  "facebook":"Facebook","tiktok":"TikTok","discord":"Discord",
                  "instagram-story":"Autre / Direct","shared-unknown":"Autre / Direct"}
PLATFORMS = {'instagram': 'Instagram', 'youtube': 'YouTube', 'facebook': 'Facebook',
             'tiktok': 'TikTok', 'discord': 'Discord', 'other': 'Autre / Direct'}
SOURCE_KEYS = set(LEGACY_SOURCES) | {'platform:'+key for key in PLATFORMS}


class DuplicateDestination(ValueError):
    def __init__(self, matches):
        self.matches = matches
        super().__init__('Cette destination existe déjà. Réutilisez le lien existant ou confirmez exceptionnellement le doublon.')


def canonical_destination(url):
    """Comparison only: never rewrite a stored or published affiliate destination.

    Query keys may be reordered, but repeated values for one key keep their order.
    All parameters, literal plus signs, fragments, schemes and path case survive.
    """
    parsed = urlsplit(url)
    unreserved = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
    def percent(value):
        return re.sub(r'%([0-9a-fA-F]{2})', lambda match: chr(int(match[1], 16))
                      if chr(int(match[1], 16)) in unreserved else '%' + match[1].upper(), value)
    host = (parsed.hostname or '').encode('idna').decode('ascii').lower().rstrip('.')
    port = parsed.port
    if (parsed.scheme.lower(), port) in {('http', 80), ('https', 443)}:
        port = None
    groups = {}
    if parsed.query:
        for parameter in parsed.query.split('&'):
            key, equals, value = parameter.partition('=')
            groups.setdefault(percent(key), []).append((bool(equals), percent(value)))
    query = tuple((key, tuple(values)) for key, values in sorted(groups.items()))
    return (parsed.scheme.lower(), host, port, percent(parsed.path or '/'), query,
            '?' in url.split('#', 1)[0], percent(parsed.fragment), '#' in url)


def duplicate_destinations(db, url, exclude=None, campaigns=False):
    target = canonical_destination(url)
    matches = []
    tracked_exclude=exclude if not campaigns else None
    rows=[dict(row) for row in db.execute('SELECT id,name,url,archived,enabled FROM tracked_links WHERE id!=? ORDER BY created_at,id', (tracked_exclude or '',))]
    if campaigns:
        rows=[{**row,'kind':'tracked'} for row in rows]
        rows.extend(dict(row) for row in db.execute("""SELECT id,internal_name AS name,url,archived,
            active AND NOT retired AS enabled,'campaign' AS kind FROM content_blocks
            WHERE type IN ('promo','featured') AND id!=? ORDER BY created_at,id""",(exclude or '',)))
    for row in rows:
        try:
            equivalent = canonical_destination(row['url']) == target
        except (ValueError, UnicodeError):
            equivalent = False
        if equivalent:
            matches.append(dict(row))
    return matches


def check_duplicate_destination(db, url, data, current=None):
    matches = duplicate_destinations(db, url, current['id'] if current else None)
    # Existing duplicates remain editable without repeatedly approving an unchanged destination.
    required = bool(matches) and (not current or canonical_destination(current['url']) != canonical_destination(url))
    if required and (data.get('allow_duplicate') is not True or
                     data.get('duplicate_ids') != sorted(row['id'] for row in matches)):
        raise DuplicateDestination(matches)
    return matches, required


def _category_integrity(db):
    if list(db.execute('PRAGMA integrity_check')) != [('ok',)] or list(db.execute('PRAGMA foreign_key_check')):
        raise ValueError('Intégrité SQLite ou références invalides : migration des catégories interrompue.')


def _category_compare(db, saved, removed=False):
    """Compare complete schemas and stream every retained value, including duplicates.

    This runs once at upgrade, with writers locked. No application projection or
    retention window is used: even unknown tables and old counters are checked.
    """
    objects = 'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'
    before, after = list(saved.execute(objects)), list(db.execute(objects))
    if removed:
        before = [row for row in before if row[:2] != ('table', 'tracked_links')]
        after = [row for row in after if row[:2] != ('table', 'tracked_links')]
    if before != after:
        raise ValueError('Le schéma utile a changé pendant la migration des catégories.')
    for (name,) in saved.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        expected = [row[1:] for row in saved.execute('PRAGMA table_xinfo('+quoted+')')]
        if removed and name == 'tracked_links':
            expected = [row for row in expected if row[0] != 'category']
        actual = [row[1:] for row in db.execute('PRAGMA table_xinfo('+quoted+')')]
        if expected != actual or list(saved.execute('PRAGMA foreign_key_list('+quoted+')')) != list(db.execute('PRAGMA foreign_key_list('+quoted+')')):
            raise ValueError('Colonnes ou contraintes modifiées : '+name)
        names = ['"'+row[0].replace('"', '""')+'"' for row in expected]
        columns = ','.join(names + ['typeof('+name+')' for name in names])
        # BINARY sorting avoids application collations hiding changed text values.
        order = ','.join('"'+row[0].replace('"', '""')+'" COLLATE BINARY' for row in expected)
        query = 'SELECT '+columns+' FROM '+quoted+' ORDER BY '+order
        missing = object()
        if any(left != right for left, right in zip_longest(db.execute(query), saved.execute(query), fillvalue=missing)):
            raise ValueError('Données utiles modifiées : '+name)


def remove_legacy_category(database):
    """Startup-only, atomic native DROP; never rebuild tables or disable FKs.

    An independent SQLite backup includes committed WAL pages. BEGIN IMMEDIATE
    excludes concurrent writers until comparison and commit have both succeeded.
    Failed or interrupted attempts retain their backup for manual recovery.
    """
    path = Path(database).resolve()
    if not path.is_file():
        return None
    target = None
    with closing(sqlite3.connect(path, timeout=10, isolation_level=None)) as db:
        if 'category' not in {row[1] for row in db.execute('PRAGMA table_info(tracked_links)')}:
            return None
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            columns = {row[1]: row for row in db.execute('PRAGMA table_xinfo(tracked_links)')}
            if 'category' not in columns:  # Another startup may have finished while acquiring the lock.
                db.rollback()
                return None
            if sqlite3.sqlite_version_info < (3, 35, 0):
                raise ValueError('SQLite 3.35.0 minimum requis pour supprimer les catégories.')
            if columns['category'][2:] != ('TEXT', 1, "''", 0, 0) or not {'id', 'name', 'url'} <= columns.keys():
                raise ValueError('Schéma de catégories inconnu : audit complémentaire requis.')
            for kind, name, table, sql in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL"):
                linked = table == 'tracked_links' or re.search(r'\btracked_links\b', sql, re.I)
                if linked and (kind in {'view', 'trigger'} or kind == 'index' and re.search(r'\bcategory\b', sql, re.I)):
                    raise ValueError('Dépendance SQLite à auditer avant migration : '+name)
            _category_integrity(db)
            if any(not isinstance(name, str) or not name.strip() for (name,) in db.execute('SELECT name FROM tracked_links')):
                raise ValueError('Un lien sans nom doit être corrigé avant la migration des catégories.')
            directory = path.parent / 'pre-category-removal' / uuid.uuid4().hex
            directory.mkdir(parents=True)  # Unique directory: never overwrite an earlier safety copy.
            partial = directory / 'analytics.db.partial'
            with closing(sqlite3.connect(path, timeout=10)) as source, closing(sqlite3.connect(partial)) as backup:
                source.backup(backup)
            with closing(sqlite3.connect(partial)) as backup:
                _category_integrity(backup)
                _category_compare(db, backup)
            target = directory / 'analytics.db'
            partial.rename(target)
            with closing(sqlite3.connect(target.as_uri()+'?mode=ro', uri=True)) as backup:
                db.execute('ALTER TABLE tracked_links DROP COLUMN category')
                _category_integrity(db)
                _category_compare(db, backup, removed=True)
            db.commit()
        except Exception as exc:
            db.rollback()
            location = str(target) if target else 'aucune copie validée'
            raise RuntimeError('Suppression des catégories annulée. Sauvegarde : '+location+'. '+str(exc)) from exc
    return target


def initialize(db):
    first_install=not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tracking_sources'").fetchone()
    first_keys=not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tracking_source_keys'").fetchone()
    db.execute("""CREATE TABLE IF NOT EXISTS tracking_sources (
        id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
        active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
        story_click_total INTEGER NOT NULL DEFAULT 0 CHECK(story_click_total >= 0),
        created_at TEXT NOT NULL)""")
    if "story_click_total" not in {row[1] for row in db.execute("PRAGMA table_info(tracking_sources)")}:
        db.execute("ALTER TABLE tracking_sources ADD COLUMN story_click_total INTEGER NOT NULL DEFAULT 0")
    db.execute("""CREATE TABLE IF NOT EXISTS tracked_links (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
        notes TEXT NOT NULL DEFAULT '',
        archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS tracked_tokens (
        token TEXT PRIMARY KEY, link_id TEXT NOT NULL REFERENCES tracked_links(id),
        source_id TEXT NOT NULL REFERENCES tracking_sources(id),
        click_total INTEGER NOT NULL DEFAULT 0 CHECK(click_total >= 0),
        created_at TEXT NOT NULL, UNIQUE(link_id,source_id))""")
    db.execute('CREATE TABLE IF NOT EXISTS tracking_source_keys(key TEXT PRIMARY KEY,source_id TEXT REFERENCES tracking_sources(id))')
    if first_install:
        for name in DEFAULT_SOURCES:
            codes=[key for key,label in LEGACY_SOURCES.items() if label==name]
            clicks=0
            if codes:
                slots=','.join('?' for _ in codes)
                clicks=db.execute("SELECT COALESCE(SUM(total),0) FROM counts WHERE kind='story' AND source IN ("+slots+")",codes).fetchone()[0]
            db.execute("INSERT INTO tracking_sources VALUES(?,?,1,?,datetime('now'))",(uuid.uuid4().hex,name,clicks))
    if first_keys:
        # Capture legacy labels once; a rename or a new namesake never changes identity.
        # Missing/ambiguous pre-upgrade identities remain unassigned, never guessed.
        for key,name in LEGACY_SOURCES.items():
            row=db.execute('SELECT id FROM tracking_sources WHERE name=?',(name,)).fetchone()
            db.execute('INSERT INTO tracking_source_keys VALUES(?,?)',(key,row['id'] if row else None))
    # Add preferred platform identities without renaming, merging or reassigning history.
    for platform, name in PLATFORMS.items():
        key = 'platform:'+platform
        if db.execute('SELECT 1 FROM tracking_source_keys WHERE key=?', (key,)).fetchone():
            continue
        row = db.execute('SELECT id FROM tracking_sources WHERE name=?', (name,)).fetchone()
        ident = row['id'] if row else uuid.uuid4().hex
        if not row:
            db.execute("INSERT INTO tracking_sources VALUES(?,?,1,0,datetime('now'))", (ident, name))
        db.execute('INSERT INTO tracking_source_keys VALUES(?,?)', (key, ident))


def platform_source_ids(db, platform):
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='tracking_source_keys'").fetchone():
        values = {row['key']: row['source_id'] for row in db.execute('SELECT * FROM tracking_source_keys')}
        return list(dict.fromkeys(value for value in [values.get('platform:'+platform), values.get(platform)] if value))
    # Compatibility with pre-migration read-only snapshots.
    return [row['id'] for row in db.execute('SELECT id FROM tracking_sources WHERE name IN (?,?)',
                                          (PLATFORMS.get(platform, ''), LEGACY_SOURCES.get(platform, '')))]


def publication_source(db, ident, platform='instagram'):
    candidates = platform_source_ids(db, platform)
    if candidates:
        slots = ','.join('?' for _ in candidates)
        # Repeated PulSe retrievals keep the earliest already-published alias.
        row = db.execute('''SELECT s.id FROM tracked_tokens t JOIN tracking_sources s ON s.id=t.source_id
            WHERE t.link_id=? AND s.active=1 AND s.id IN ('''+slots+''') ORDER BY t.created_at,t.rowid LIMIT 1''', [ident, *candidates]).fetchone()
        if row:
            return row
        preferred = db.execute('SELECT source_id FROM tracking_source_keys WHERE key=?', ('platform:'+platform,)).fetchone()
        for source_id in ([preferred['source_id']] if preferred else candidates):
            row = db.execute('SELECT id FROM tracking_sources WHERE id=? AND active=1', (source_id,)).fetchone()
            if row:
                return row
    raise ValueError('Source '+PLATFORMS.get(platform, platform)+' indisponible. Réactivez-la dans la gestion des sources.')

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
    bindings = {row['source_id']: row['key'].split(':', 1)[1] for row in db.execute("SELECT * FROM tracking_source_keys WHERE key LIKE 'platform:%'") if row['source_id']}
    legacy = {row['source_id'] for row in db.execute('SELECT * FROM tracking_source_keys') if row['key'] in LEGACY_SOURCES}
    for row in rows:
        row['platform'] = bindings.get(row['id'], '')
        row['historical'] = not row['platform'] and (row['id'] in legacy or row['name'] in DEFAULT_SOURCES)
    order = list(PLATFORMS)
    rows.sort(key=lambda row: (0 if row['platform'] else 2 if row['historical'] else 1,
                              order.index(row['platform']) if row['platform'] in order else 100, row['name'].casefold()))
    return rows

def add_source(db,data,now):
    name=text_field(data,"name",100,True)
    ident=uuid.uuid4().hex
    try:db.execute("INSERT INTO tracking_sources VALUES(?,?,1,0,?)",(ident,name,now))
    except sqlite3.IntegrityError as exc:raise ValueError('Une source porte déjà ce nom.') from exc
    return {"id":ident,"name":name,"active":True}

def edit_source(db,ident,data):
    current=db.execute("SELECT * FROM tracking_sources WHERE id=?",(ident,)).fetchone()
    if not current:raise ValueError("Source introuvable")
    name=text_field(data,"name",100,True)
    try:db.execute("UPDATE tracking_sources SET name=? WHERE id=?",(name,ident))
    except sqlite3.IntegrityError as exc:raise ValueError('Une source porte déjà ce nom.') from exc
    return {"id":ident,"name":name}

def remove_source(db,ident):
    item=db.execute("SELECT id FROM tracking_sources WHERE id=?",(ident,)).fetchone()
    if not item:raise ValueError("Source introuvable")
    clicks=db.execute("SELECT COALESCE(SUM(click_total),0) FROM tracked_tokens WHERE source_id=?",(ident,)).fetchone()[0]
    clicks+=db.execute("SELECT story_click_total FROM tracking_sources WHERE id=?",(ident,)).fetchone()[0]
    published=db.execute('SELECT 1 FROM tracked_tokens WHERE source_id=? LIMIT 1',(ident,)).fetchone()
    published=published or db.execute('SELECT 1 FROM tracking_source_keys WHERE source_id=? LIMIT 1',(ident,)).fetchone()
    published=published or db.execute('SELECT 1 FROM short_aliases WHERE source=? LIMIT 1',('tracked:'+ident,)).fetchone()
    if clicks or published:
        db.execute("UPDATE tracking_sources SET active=0 WHERE id=?",(ident,))
        return {"action":"archived","clicks":clicks}
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
            "notes":text_field(data,"notes",800)}

def create_link(db,data,url_valid,now):
    fields=link_input(data,url_valid);ident=uuid.uuid4().hex
    db.execute("INSERT INTO tracked_links(id,name,url,notes,created_at,updated_at) VALUES(?,?,?,?,?,?)",
               (ident,fields["name"],fields["url"],fields["notes"],now,now))
    return {"id":ident,**fields}

def update_link(db,ident,data,url_valid,now):
    fields=link_input(data,url_valid)
    if not db.execute("""UPDATE tracked_links SET name=?,url=?,notes=?,updated_at=?
                      WHERE id=?""",(fields["name"],fields["url"],fields["notes"],now,ident)).rowcount:
        raise ValueError("Lien introuvable")
    return {"id":ident,**fields}

def update_titles(db, data, now):
    """Atomically rename existing, non-archived links without touching destinations.

    The caller owns a BEGIN IMMEDIATE transaction. Stale titles or modifications
    reject the entire batch; short URLs, partners, source tokens and click totals
    are never updated by this operation.
    """
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError('Liste de titres invalide.')
    changes = data['items']
    if not 1 <= len(changes) <= 2000:
        raise ValueError('Sélectionnez entre 1 et 2 000 liens.')
    validated = []
    seen = set()
    for item in changes:
        if not isinstance(item, dict):
            raise ValueError('Ligne de titre invalide.')
        ident = item.get('id')
        if not isinstance(ident, str) or not IDENT.fullmatch(ident) or ident in seen:
            raise ValueError('Identifiant de lien invalide ou répété.')
        seen.add(ident)
        name = text_field(item, 'name', 160, True)
        expected_name = text_field(item, 'expected_name', 160, True)
        updated = text_field(item, 'expected_updated_at', 80, True)
        current = db.execute('SELECT name,updated_at,archived FROM tracked_links WHERE id=?', (ident,)).fetchone()
        if not current or current['archived']:
            raise ValueError('Un lien est introuvable ou archivé. Actualisez la liste.')
        if current['name'] != expected_name or current['updated_at'] != updated:
            raise ValueError('Un lien a changé depuis l’analyse. Actualisez les titres avant de valider.')
        validated.append((ident, name, expected_name, updated))
    changed = []
    for ident, name, old, updated in validated:
        if name == old:
            continue
        affected = db.execute('''UPDATE tracked_links SET name=?,updated_at=?
            WHERE id=? AND name=? AND updated_at=? AND archived=0''',
            (name, now, ident, old, updated)).rowcount
        if affected != 1:
            raise ValueError('Un lien a changé pendant l’enregistrement. Réessayez après actualisation.')
        changed.append({'id': ident, 'name': name})
    return {'updated': len(changed), 'items': changed}


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
        db.execute("UPDATE tracking_sources SET story_click_total=story_click_total+1 WHERE id=(SELECT source_id FROM tracking_source_keys WHERE key=?)",(source,))

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
    rows=[dict(r) for r in db.execute("""SELECT id,name,url,notes,archived,enabled,created_at,updated_at
        FROM tracked_links ORDER BY created_at DESC""")]
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
