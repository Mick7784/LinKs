"""Optional affiliate rules; saved destinations are immutable until explicitly edited."""
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, quote, unquote, unquote_plus
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
    db.execute('''CREATE TABLE IF NOT EXISTS campaign_partners(
        campaign_id TEXT PRIMARY KEY REFERENCES content_blocks(id) ON DELETE CASCADE,
        partner_id TEXT REFERENCES affiliate_partners(id) ON DELETE RESTRICT,
        original_url TEXT NOT NULL, final_url TEXT NOT NULL)''')
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
    # Single-pass substitution, with URL components kept intact. Query templates
    # replace their own keys once, without re-encoding unrelated original bytes.
    def substitute(value, context=''):
        def token(match):
            prefix=context+value[:match.start()]
            in_query='?' in prefix and '#' not in prefix and '=' in prefix.rsplit('&',1)[-1]
            text=url if match[1]=='url' else code
            return quote(text,safe=':/' if match[1]=='url' else '') if in_query else text
        return re.sub(r'\{(url|code)\}',token,value)
    if template.startswith(('{url}?','{url}&')):
        suffix=substitute('?'+template[6:])
        added,has_fragment,new_fragment=suffix[1:].partition('#')
        base,original_hash,fragment=url.partition('#')
        path,original_query,query=base.partition('?')
        parameters=[part for part in added.split('&') if part]
        keys={unquote_plus(part.partition('=')[0]) for part in parameters}
        kept=[part for part in query.split('&') if unquote_plus(part.partition('=')[0]) not in keys] if query else []
        combined='&'.join(kept+parameters)
        result=path+('?' if combined or original_query else '')+combined
        if has_fragment or original_hash:result+='#'+(new_fragment if has_fragment else fragment)
    elif template.startswith('{url}#'):
        result=url.partition('#')[0]+'#'+substitute(template[6:])
    else:
        result=substitute(template)
        if template.count('{url}')==1:
            before,_,after=template.partition('{url}')
            prefix,suffix=substitute(before),substitute(after,before+'{url}')
            if url.startswith(prefix) and (not suffix or url.endswith(suffix)):
                nested=url[len(prefix):len(url)-len(suffix) if suffix else None]
                if http_url(unquote(nested)):result=url  # A current-code wrapper is already applied.
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
    for row in db.execute('''SELECT p.*, COUNT(a.link_id)+(SELECT COUNT(*) FROM campaign_partners c WHERE c.partner_id=p.id) AS links,
            (SELECT COUNT(*) FROM campaign_partners c WHERE c.partner_id=p.id) AS campaigns FROM affiliate_partners p
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
        raise ValueError('Ce partenaire est associé à des liens ou campagnes. Retirez ces associations avant de le supprimer.')
    try:
        changed = db.execute('DELETE FROM affiliate_partners WHERE id=?', (ident,)).rowcount
    except sqlite3.IntegrityError as exc:
        raise ValueError('Ce partenaire est associé à des liens ou campagnes et ne peut pas être supprimé.') from exc
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


def resolve_destination(db, data, current=None, metadata=None, url_valid=http_url, allow_direct=False):
    """Shared partner/destination resolver for tracked links and campaigns."""
    origin = text_field(data, 'url', 2000, True)
    if not http_url(origin) and not (allow_direct and url_valid(origin)):
        raise ValueError('URL d’origine HTTP(S) valide requise.')
    partner_id = (detect(db, origin) if http_url(origin) else '') if data.get('detect') is True else text_field(data, 'partner_id', 32)
    partner = db.execute('SELECT * FROM affiliate_partners WHERE id=?', (partner_id,)).fetchone() if partner_id else None
    if partner_id and not partner:
        raise ValueError('Partenaire introuvable.')
    if current and origin==current['url'] and partner_id==metadata['partner_id']:
        # Echoed final URLs are reapplied from their captured origin, never wrapped twice.
        origin=metadata['original_url']
    preserve = (current and data.get('apply_partner') is not True
                and origin == metadata['original_url'] and partner_id == metadata['partner_id'])
    final = current['url'] if preserve else build_url(partner['template'], partner['code'], origin) if partner else origin
    if len(final) > 2000:
        raise ValueError('La destination finale dépasse 2 000 caractères.')
    if not url_valid(final):
        raise ValueError('Destination finale HTTP(S) valide requise, extérieure à cette instance.')
    return {'url':final,'original_url':origin,'partner_id':partner_id,
            'previous_url':current['url'] if current else '', 'changed':bool(current and current['url']!=final)}


def preview_tracked(db, data, ident=None, url_valid=http_url):
    current = db.execute('SELECT * FROM tracked_links WHERE id=?', (ident,)).fetchone() if ident else None
    if ident and not current:raise ValueError('Lien introuvable.')
    result=resolve_destination(db,data,current,link_metadata(db,ident,current['url']) if current else None,url_valid)
    duplicates = tracked_links.duplicate_destinations(db, result['url'], ident)
    required = bool(duplicates) and (not current or tracked_links.canonical_destination(current['url']) != tracked_links.canonical_destination(result['url']))
    return {**result,
            'duplicates': duplicates, 'duplicate_confirmation_required': required}


def confirm_preview(data,result):
    if data.get('expected_url')!=result['url'] or (result['previous_url'] and data.get('previous_url')!=result['previous_url']):
        raise ValueError('L’aperçu ou la destination a changé. Vérifiez à nouveau l’URL finale avant d’enregistrer.')
    if result['changed'] and data.get('confirm_destination') is not True:
        raise ValueError('Confirmez explicitement le remplacement de la destination existante.')


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
    confirm_preview(data,result)
    tracked_links.check_duplicate_destination(db, result['url'], data, current)
    fields = {**data, 'url': result['url']}
    saved = (tracked_links.update_link(db, ident, fields, url_valid, now) if ident
             else tracked_links.create_link(db, fields, url_valid, now))
    db.execute('DELETE FROM tracked_link_partners WHERE link_id=?', (saved['id'],))
    if result['partner_id']:
        db.execute('INSERT INTO tracked_link_partners(link_id,partner_id,original_url) VALUES(?,?,?)',
                   (saved['id'], result['partner_id'], result['original_url']))
    return {**saved, **result, 'id': saved['id']}


def campaign_metadata(db, ident, destination):
    row=db.execute('SELECT * FROM campaign_partners WHERE campaign_id=?',(ident,)).fetchone()
    return {'partner_id':(row['partner_id'] or '') if row else '',
            'original_url':row['original_url'] if row else destination,
            'final_url':destination,'affiliate_configured':bool(row)}


def preview_campaign(db,data,ident=None,url_valid=http_url):
    current=db.execute("SELECT * FROM content_blocks WHERE id=?",(ident,)).fetchone() if ident else None
    if ident and not current:raise ValueError('Campagne introuvable.')
    result=resolve_destination(db,data,current,campaign_metadata(db,ident,current['url']) if current else None,url_valid,allow_direct=True)
    duplicates=tracked_links.duplicate_destinations(db,result['url'],ident,campaigns=True)
    required=bool(duplicates) and (not current or tracked_links.canonical_destination(current['url'])!=tracked_links.canonical_destination(result['url']))
    return {**result,'duplicates':duplicates,'duplicate_confirmation_required':required}


def check_campaign_preview(data,result):
    confirm_preview(data,result)
    if result['duplicate_confirmation_required'] and (data.get('allow_duplicate') is not True or
            data.get('duplicate_ids')!=sorted(row['kind']+':'+row['id'] for row in result['duplicates'])):
        raise ValueError('Destination déjà utilisée : réutilisez une fiche existante ou confirmez explicitement le doublon.')


def save_campaign_metadata(db,ident,result):
    db.execute('''INSERT INTO campaign_partners VALUES(?,?,?,?) ON CONFLICT(campaign_id) DO UPDATE SET
        partner_id=excluded.partner_id,original_url=excluded.original_url,final_url=excluded.final_url''',
        (ident,result['partner_id'] or None,result['original_url'],result['url']))


def merge_campaign_backup(db,tables):
    incoming={row['campaign_id']:row for row in tables['campaign_partners']}
    campaigns={row['id']:row for row in tables['content_blocks']}
    # A restore must not roll back published destination/provenance snapshots.
    for old in db.execute('SELECT * FROM campaign_partners'):
        current=db.execute('SELECT url FROM content_blocks WHERE id=?',(old['campaign_id'],)).fetchone()
        row=dict(old);row['final_url']=current['url']
        incoming[row['campaign_id']]=row;campaigns[row['campaign_id']]['url']=current['url']
    tables['campaign_partners']=list(incoming.values())
    partners={row['id'] for row in tables['affiliate_partners']}
    for row in tables['campaign_partners']:
        campaign=campaigns.get(row['campaign_id'])
        if (not campaign or campaign['type'] not in {'promo','featured'} or
                row['partner_id'] is not None and row['partner_id'] not in partners or row['final_url']!=campaign['url']):
            raise ValueError('Association de campagne invalide dans la sauvegarde.')


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
