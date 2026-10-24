"""Optional affiliate configuration. No link rewriting or automatic detection."""
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit
from tracked_links import text_field

DEFAULTS = (
    ('Domadoo', '117', ['domadoo.fr'], '{url}?domid={code}'),
    ('Reolink', '1404', ['reolink.com'], '{url}?aff={code}'),
    ('Sanyipace', 'DomotiK', ['sanyipace.com', 'sanyipace.eu'], '{url}?ref={code}'),
)


def initialize(db):
    first = not db.execute("SELECT 1 FROM sqlite_master WHERE name='affiliate_partners' AND type='table'").fetchone()
    db.execute('''CREATE TABLE IF NOT EXISTS affiliate_partners(
        id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
        code TEXT NOT NULL, domains TEXT NOT NULL, template TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    # Association storage is reserved for the next step; no current link is attached.
    db.execute('''CREATE TABLE IF NOT EXISTS tracked_link_partners(
        link_id TEXT PRIMARY KEY REFERENCES tracked_links(id),
        partner_id TEXT NOT NULL REFERENCES affiliate_partners(id) ON DELETE RESTRICT)''')
    if first:
        now = datetime.now(timezone.utc).isoformat()
        for name, code, domains, template in DEFAULTS:
            ident = uuid.uuid5(uuid.NAMESPACE_URL, 'links:affiliate-partner:' + name.lower()).hex
            db.execute('INSERT OR IGNORE INTO affiliate_partners VALUES(?,?,?,?,?,?,?)',
                       (ident, name, code, json.dumps(domains), template, now, now))


def http_url(value):
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in {'http', 'https'} and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and not re.search(r'[\s\x00-\x1f\x7f]', value) and parsed.port != 0)
    except ValueError:
        return False


def normalize_domains(value):
    if isinstance(value, str):
        value = re.split(r'[\s,;]+', value.strip()) if value.strip() else []
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError('Domaines : 50 noms de domaine maximum.')
    result = []
    for domain in value:
        if not isinstance(domain, str):
            raise ValueError('Nom de domaine invalide.')
        try:
            domain = domain.strip().lower().rstrip('.').encode('idna').decode('ascii')
        except UnicodeError as exc:
            raise ValueError('Nom de domaine invalide.') from exc
        if (len(domain) > 253 or '.' not in domain or
                any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in domain.split('.'))):
            raise ValueError('Utilisez des domaines seuls, par exemple boutique.fr, sans https:// ni chemin.')
        if domain not in result:
            result.append(domain)
    return result


def build_url(template, code, url):
    if not isinstance(url, str) or len(url) > 2000 or not http_url(url):
        raise ValueError('URL de test HTTP(S) valide requise.')
    # Single-pass substitution: braces in a supplied URL/code are literal data.
    result = re.sub(r'\{(url|code)\}', lambda match: url if match[1] == 'url' else code, template)
    if len(result) > 8192 or not http_url(result):
        raise ValueError('Le modèle doit produire une URL HTTP(S) valide.')
    return result


def partner_input(data):
    if not isinstance(data, dict):
        raise ValueError('Partenaire invalide.')
    fields = {key: text_field(data, key, limit, required) for key, limit, required in
              [('name', 100, True), ('code', 500, False), ('template', 4000, True)]}
    fields['domains'] = normalize_domains(data.get('domains', []))
    if re.search(r'\{[^{}]*\}', fields['template'].replace('{url}', '').replace('{code}', '')):
        raise ValueError('Variables disponibles : {url} et {code}.')
    build_url(fields['template'], fields['code'], 'https://example.com/produit')
    return fields


def rows(db):
    result = []
    for row in db.execute('''SELECT p.*, COUNT(a.link_id) AS links FROM affiliate_partners p
            LEFT JOIN tracked_link_partners a ON a.partner_id=p.id GROUP BY p.id ORDER BY p.name COLLATE NOCASE'''):
        value = dict(row)
        value['domains'] = json.loads(value['domains'])
        result.append(value)
    return result


def save(db, data, now, ident=None):
    fields = partner_input(data)
    if ident and not db.execute('SELECT 1 FROM affiliate_partners WHERE id=?', (ident,)).fetchone():
        raise ValueError('Partenaire introuvable.')
    ident = ident or uuid.uuid4().hex
    try:
        if db.execute('SELECT 1 FROM affiliate_partners WHERE id=?', (ident,)).fetchone():
            db.execute('UPDATE affiliate_partners SET name=?,code=?,domains=?,template=?,updated_at=? WHERE id=?',
                       (fields['name'], fields['code'], json.dumps(fields['domains']), fields['template'], now, ident))
        else:
            db.execute('INSERT INTO affiliate_partners VALUES(?,?,?,?,?,?,?)',
                       (ident, fields['name'], fields['code'], json.dumps(fields['domains']), fields['template'], now, now))
    except sqlite3.IntegrityError as exc:
        raise ValueError('Un partenaire porte déjà ce nom.') from exc
    return {'id': ident, **fields}


def remove(db, ident):
    if db.execute('SELECT 1 FROM tracked_link_partners WHERE partner_id=? LIMIT 1', (ident,)).fetchone():
        raise ValueError('Ce partenaire est associé à des liens. Retirez ces associations avant de le supprimer.')
    try:
        changed = db.execute('DELETE FROM affiliate_partners WHERE id=?', (ident,)).rowcount
    except sqlite3.IntegrityError as exc:
        raise ValueError('Ce partenaire est associé à des liens et ne peut pas être supprimé.') from exc
    if not changed:
        raise ValueError('Partenaire introuvable.')
    return {'action': 'deleted'}


def merge_backup(db, tables):
    # A restore must not orphan links or discard partners created since the backup.
    incoming = {row['id'] for row in tables['affiliate_partners']}
    tables['affiliate_partners'].extend(dict(row) for row in db.execute('SELECT * FROM affiliate_partners') if row['id'] not in incoming)
    associations = {row['link_id']: row['partner_id'] for row in tables['tracked_link_partners']}
    for row in db.execute('SELECT * FROM tracked_link_partners'):
        if row['link_id'] in associations and associations[row['link_id']] != row['partner_id']:
            raise ValueError('Une association de partenaire existante ne peut pas être réattribuée par restauration.')
        if row['link_id'] not in associations:
            tables['tracked_link_partners'].append(dict(row))
    links = {row['id'] for row in tables['tracked_links']}
    partners = {row['id'] for row in tables['affiliate_partners']}
    if any(row['link_id'] not in links or row['partner_id'] not in partners for row in tables['tracked_link_partners']):
        raise ValueError('Association de partenaire invalide dans la sauvegarde.')
