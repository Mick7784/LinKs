"""Optional affiliate rules; saved destinations are immutable until explicitly edited."""
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit
from tracked_links import text_field
import tracked_links

DEFAULTS = (
    ('Domadoo', '117', ['domadoo.fr'], '{url}?domid={code}'),
    ('Reolink', '1404', ['reolink.com'], '{url}?aff={code}'),
    ('Sanyipace', 'DomotiK', ['sanyipacetoilet.com'], '{url}?ref={code}'),
)
SANYIPACE_MIGRATION = 'affiliate.sanyipace_domain_v1'


def initialize(db):
    first = not db.execute("SELECT 1 FROM sqlite_master WHERE name='affiliate_partners' AND type='table'").fetchone()
    db.execute('''CREATE TABLE IF NOT EXISTS affiliate_partners(
        id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
        code TEXT NOT NULL, domains TEXT NOT NULL, template TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS tracked_link_partners(
        link_id TEXT PRIMARY KEY REFERENCES tracked_links(id),
        partner_id TEXT NOT NULL REFERENCES affiliate_partners(id) ON DELETE RESTRICT)''')
    if 'original_url' not in {row[1] for row in db.execute('PRAGMA table_info(tracked_link_partners)')}:
        db.execute("ALTER TABLE tracked_link_partners ADD COLUMN original_url TEXT NOT NULL DEFAULT ''")
    if first:
        now = datetime.now(timezone.utc).isoformat()
        for name, code, domains, template in DEFAULTS:
            ident = uuid.uuid5(uuid.NAMESPACE_URL, 'links:affiliate-partner:' + name.lower()).hex
            db.execute('INSERT OR IGNORE INTO affiliate_partners VALUES(?,?,?,?,?,?,?)',
                       (ident, name, code, json.dumps(domains), template, now, now))
    if not db.execute('SELECT 1 FROM settings WHERE key=?', (SANYIPACE_MIGRATION,)).fetchone():
        ident = uuid.uuid5(uuid.NAMESPACE_URL, 'links:affiliate-partner:sanyipace').hex
        row = db.execute('SELECT domains FROM affiliate_partners WHERE id=?', (ident,)).fetchone()
        if row:
            domains = corrected_sanyipace_domains(json.loads(row['domains']))
            db.execute('UPDATE affiliate_partners SET domains=? WHERE id=?', (json.dumps(domains), ident))
        db.execute('INSERT INTO settings VALUES(?,?)', (SANYIPACE_MIGRATION, '1'))


def corrected_sanyipace_domains(domains):
    # Only domains shipped by step 3 on the seeded partner are replaced. Extra custom
    # domains, names, codes and templates remain intact; fully custom lists stay intact.
    old = {'sanyipace.com', 'sanyipace.eu'}
    if old.intersection(domains):
        return list(dict.fromkeys(['sanyipacetoilet.com'] + [domain for domain in domains if domain not in old]))
    return domains


def http_url(value):
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in {'http', 'https'} and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and '\\' not in value and not re.search(r'[\s\x00-\x1f\x7f]', value) and parsed.port != 0)
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


def detect(db, url):
    if not http_url(url):
        raise ValueError('URL d’origine HTTP(S) valide requise.')
    try:
        host = urlsplit(url).hostname.rstrip('.').encode('idna').decode('ascii').lower()
    except UnicodeError as exc:
        raise ValueError('Domaine de l’URL invalide.') from exc
    matches = [(len(domain), row['id']) for row in rows(db) for domain in row['domains']
               if host == domain or host.endswith('.' + domain)]
    if not matches:
        return ''
    longest = max(length for length, ident in matches)
    candidates = {ident for length, ident in matches if length == longest}
    if len(candidates) != 1:
        raise ValueError('Plusieurs partenaires correspondent à ce domaine. Choisissez-en un manuellement.')
    return candidates.pop()


def link_metadata(db, ident, destination):
    row = db.execute('SELECT * FROM tracked_link_partners WHERE link_id=?', (ident,)).fetchone()
    return {'partner_id': row['partner_id'] if row else '',
            'original_url': (row['original_url'] if row else '') or destination}


def list_tracked(db, start=None, end=None):
    return [{**row, **link_metadata(db, row['id'], row['url'])} for row in tracked_links.list_links(db, start, end)]


def preview_tracked(db, data, ident=None, url_valid=http_url):
    origin = text_field(data, 'url', 2000, True)
    if not http_url(origin):
        raise ValueError('URL d’origine HTTP(S) valide requise.')
    current = db.execute('SELECT * FROM tracked_links WHERE id=?', (ident,)).fetchone() if ident else None
    if ident and not current:
        raise ValueError('Lien introuvable.')
    partner_id = detect(db, origin) if data.get('detect') is True else text_field(data, 'partner_id', 32)
    partner = db.execute('SELECT * FROM affiliate_partners WHERE id=?', (partner_id,)).fetchone() if partner_id else None
    if partner_id and not partner:
        raise ValueError('Partenaire introuvable.')
    metadata = link_metadata(db, ident, current['url']) if current else None
    preserve = (current and data.get('apply_partner') is not True
                and origin == metadata['original_url'] and partner_id == metadata['partner_id'])
    final = current['url'] if preserve else build_url(partner['template'], partner['code'], origin) if partner else origin
    if len(final) > 2000:
        raise ValueError('La destination finale dépasse 2 000 caractères.')
    if not url_valid(final):
        raise ValueError('Destination finale HTTP(S) valide requise, extérieure à cette instance.')
    duplicates = tracked_links.duplicate_destinations(db, final, ident)
    required = bool(duplicates) and (not current or tracked_links.canonical_destination(current['url']) != tracked_links.canonical_destination(final))
    return {'url': final, 'original_url': origin, 'partner_id': partner_id,
            'previous_url': current['url'] if current else '', 'changed': bool(current and current['url'] != final),
            'duplicates': duplicates, 'duplicate_confirmation_required': required}


def save_tracked(db, data, url_valid, now, ident=None):
    current = db.execute('SELECT * FROM tracked_links WHERE id=?', (ident,)).fetchone() if ident else None
    if 'partner_id' not in data:
        # Legacy API and PulSe callers supply an explicit destination, never a rule.
        fields = tracked_links.link_input(data, url_valid)
        tracked_links.check_duplicate_destination(db, fields['url'], data, current)
        result = (tracked_links.update_link(db, ident, data, url_valid, now) if ident
                  else tracked_links.create_link(db, data, url_valid, now))
        if current and current['url'] != result['url']:
            db.execute('DELETE FROM tracked_link_partners WHERE link_id=?', (ident,))
        return result
    result = preview_tracked(db, data, ident, url_valid)
    if data.get('expected_url') != result['url'] or (current and data.get('previous_url') != current['url']):
        raise ValueError('L’aperçu ou la destination a changé. Vérifiez à nouveau l’URL finale avant d’enregistrer.')
    if result['changed'] and data.get('confirm_destination') is not True:
        raise ValueError('Confirmez explicitement le remplacement de la destination existante.')
    tracked_links.check_duplicate_destination(db, result['url'], data, current)
    fields = {**data, 'url': result['url']}
    saved = (tracked_links.update_link(db, ident, fields, url_valid, now) if ident
             else tracked_links.create_link(db, fields, url_valid, now))
    db.execute('DELETE FROM tracked_link_partners WHERE link_id=?', (saved['id'],))
    if result['partner_id']:
        db.execute('INSERT INTO tracked_link_partners(link_id,partner_id,original_url) VALUES(?,?,?)',
                   (saved['id'], result['partner_id'], result['original_url']))
    return {**saved, **result, 'id': saved['id']}


def merge_backup(db, tables):
    # A restore must not orphan links or discard partners created since the backup.
    incoming = {row['id'] for row in tables['affiliate_partners']}
    tables['affiliate_partners'].extend(dict(row) for row in db.execute('SELECT * FROM affiliate_partners') if row['id'] not in incoming)
    associations = {row['link_id']: row for row in tables['tracked_link_partners']}
    for row in db.execute('SELECT * FROM tracked_link_partners'):
        if row['link_id'] in associations and associations[row['link_id']]['partner_id'] != row['partner_id']:
            raise ValueError('Une association de partenaire existante ne peut pas être réattribuée par restauration.')
        if row['link_id'] not in associations:
            tables['tracked_link_partners'].append(dict(row))
        else:
            associations[row['link_id']]['original_url'] = row['original_url']
    links = {row['id'] for row in tables['tracked_links']}
    partners = {row['id'] for row in tables['affiliate_partners']}
    if any(row['link_id'] not in links or row['partner_id'] not in partners for row in tables['tracked_link_partners']):
        raise ValueError('Association de partenaire invalide dans la sauvegarde.')
