"""Description templates and durable documents, sharing the existing SQLite transaction.

No merchant request, link creation, source creation or redirect here.
References are stable catalogue IDs; missing references remain explicit problems.
"""
import copy
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import affiliate_partners

TABLES = ('description_templates', 'description_drafts', 'description_versions')
DEFAULT_ID = 'domotik-youtube'
KEY = re.compile(r'[a-zA-Z0-9_-]{1,80}')
MAX_TEXT = 100000


class Conflict(ValueError):
    pass


def stamp():
    return datetime.now(timezone.utc).isoformat()


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def initialize(db, seed=True):
    for table in TABLES:
        db.execute('CREATE TABLE IF NOT EXISTS '+table+'''(
            id TEXT PRIMARY KEY, revision INTEGER NOT NULL CHECK(revision>0),
            payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            deleted INTEGER NOT NULL DEFAULT 0 CHECK(deleted IN (0,1)))''')
    # The tombstone prevents a deleted default from reappearing at every restart.
    if seed and not db.execute('SELECT 1 FROM description_templates WHERE id=?', (DEFAULT_ID,)).fetchone():
        data = json.loads(Path(__file__).with_name('description_default.json').read_text(encoding='utf-8'))
        insert(db, TABLES[0], validate_template(data), DEFAULT_ID)


def text(data, key, maximum, required=False):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value) > maximum or '\x00' in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value) or (required and not value.strip()):
        raise ValueError('Champ invalide : '+key)
    return value  # Editable text and URLs are never stripped or normalized.


def ident(value):
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise ValueError('Identifiant invalide.')
    return value


def flag(data, key):
    value = data.get(key, False)
    if type(value) is not bool:
        raise ValueError('Option invalide : '+key)
    return value


def sequence(value, limit):
    if not isinstance(value, list) or len(value) > limit or any(not isinstance(x, dict) for x in value):
        raise ValueError('Liste invalide.')
    return value


def validate_template(data):
    if not isinstance(data, dict):
        raise ValueError('Modèle invalide.')
    result = {'name': text(data, 'name', 160, True), 'platform': text(data, 'platform', 80, True), 'sections': []}
    used = set()

    def unique(item):
        key = ident(item.get('id'))
        if key in used:
            raise ValueError('Les identifiants des sections et liens doivent être uniques.')
        used.add(key)
        return key

    def links(items):
        values = []
        for item in sequence(items, 50):
            url = text(item, 'reference_url', 2000)
            if url and not affiliate_partners.http_url(url):
                raise ValueError('URL de référence HTTP(S) invalide.')
            link_id, source_id = text(item, 'link_id', 80), text(item, 'source_id', 80)
            if link_id: ident(link_id)
            if source_id: ident(source_id)
            values.append({'id': unique(item), 'label': text(item, 'label', 240), 'reference_url': url,
                           'link_id': link_id, 'source_id': source_id})
        return values

    for item in sequence(data.get('sections'), 50):
        mode = item.get('mode')
        if mode not in {'manual', 'permanent', 'smart'}:
            raise ValueError('Mode de section invalide.')
        section = {'id': unique(item), 'name': text(item, 'name', 160, True),
                   'heading': text(item, 'heading', 240), 'text': text(item, 'text', MAX_TEXT),
                   'after_text': text(item, 'after_text', MAX_TEXT),
                   'mode': mode, 'hide_if_empty': flag(item, 'hide_if_empty'),
                   'links': links(item.get('links', [])), 'merchants': []}
        for merchant in sequence(item.get('merchants', []), 30):
            partner_id = text(merchant, 'partner_id', 80)
            if partner_id: ident(partner_id)
            section['merchants'].append({'id': unique(merchant), 'name': text(merchant, 'name', 160, True),
                'heading': text(merchant, 'heading', 240), 'text': text(merchant, 'text', MAX_TEXT),
                'after_text': text(merchant, 'after_text', MAX_TEXT),
                'partner_id': partner_id, 'hide_if_empty': flag(merchant, 'hide_if_empty'),
                'links': links(merchant.get('links', []))})
        result['sections'].append(section)
    if len(packed(result)) > 500000:
        raise ValueError('Modèle trop volumineux.')
    return result


def decode(row):
    return {**json.loads(row['payload']), 'id': row['id'], 'revision': row['revision'],
            'created_at': row['created_at'], 'updated_at': row['updated_at']}


def get(db, table, key):
    row = db.execute('SELECT * FROM '+table+' WHERE id=? AND deleted=0', (ident(key),)).fetchone()
    if not row:
        raise ValueError('Élément introuvable ou supprimé.')
    return decode(row)


def rows(db, table):
    return [decode(row) for row in db.execute('SELECT * FROM '+table+' WHERE deleted=0 ORDER BY updated_at DESC,id')]


def insert(db, table, payload, key=None):
    key, now = key or uuid.uuid4().hex, stamp()
    db.execute('INSERT INTO '+table+' VALUES(?,1,?,?,?,0)', (key, packed(payload), now, now))
    return get(db, table, key)


def update(db, table, key, payload, revision, deleted=False):
    if table == TABLES[2]:
        raise ValueError('Une version finalisée est immuable.')
    if type(revision) is not int or revision < 1:
        raise ValueError('Révision attendue requise.')
    changed = db.execute('UPDATE '+table+''' SET payload=?,revision=revision+1,updated_at=?,deleted=?
        WHERE id=? AND revision=? AND deleted=0''', (packed(payload), stamp(), int(deleted), ident(key), revision)).rowcount
    if changed != 1:
        raise Conflict('Cet élément a changé ailleurs. Votre saisie est conservée ; rechargez avant de réessayer.')
    return {'deleted': True} if deleted else get(db, table, key)


def catalogue(db):
    # Reading aliases must never visit a redirect, count a click or allocate a token.
    items = affiliate_partners.list_tracked(db)
    for item in items:
        item['publications'] = [dict(row) for row in db.execute('''SELECT t.source_id,s.name AS source_name,
            s.active,a.code FROM tracked_tokens t JOIN tracking_sources s ON s.id=t.source_id
            JOIN short_aliases a ON a.target_token=t.token AND a.source='tracked:'||t.source_id
            WHERE t.link_id=? AND a.revoked=0 ORDER BY a.created_at,a.code''', (item['id'],))]
    return {'items': items, 'partners': affiliate_partners.rows(db)}


def resolved_link(db, binding, origin):
    if not binding['link_id'] or not binding['source_id']:
        return None, 'Associer une fiche LinKs et un lien de publication existant.'
    row = db.execute('SELECT url,enabled,archived FROM tracked_links WHERE id=?', (binding['link_id'],)).fetchone()
    if not row or not row['enabled'] or row['archived']:
        return None, 'Fiche LinKs absente, archivée ou suspendue.'
    # No rule application: especially no Amazon transformation or silent redirection.
    from urllib.parse import urlsplit
    host = (urlsplit(row['url']).hostname or '').lower()
    if host in {'amzn.to', 'link.amazon'} or re.search(r'(^|\.)amazon\.[a-z.]+$', host):
        return None, 'Lien Amazon : insertion directe à valider dans l’éditeur, sans statistiques de clics LinKs.'
    alias = db.execute('''SELECT a.code FROM tracked_tokens t JOIN tracking_sources s ON s.id=t.source_id
        JOIN short_aliases a ON a.target_token=t.token AND a.source='tracked:'||t.source_id
        WHERE t.link_id=? AND t.source_id=? AND s.active=1 AND a.revoked=0
        ORDER BY a.created_at,a.code LIMIT 1''', (binding['link_id'], binding['source_id'])).fetchone()
    if not alias or not origin:
        return None, 'Lien de publication existant indisponible. Aucun jeton créé.'
    return origin+'/'+alias['code'], None


def render(db, template, origin):
    problems, output, anchors, initial = [], [], [], {}

    def body(item):
        parts = [item['text']] if item['text'] else []
        for binding in item['links']:
            url, problem = resolved_link(db, binding, origin)
            if problem:
                problems.append({'id': binding['id'], 'label': binding['label'], 'message': problem})
            else:
                parts.append(binding['label']+url)
        value = '\n'.join(parts)
        return value + ('\n\n' if value and item['after_text'] else '') + item['after_text']

    for section in template['sections']:
        content = body(section)
        for merchant in section['merchants']:
            if merchant['partner_id'] and not db.execute('SELECT 1 FROM affiliate_partners WHERE id=?', (merchant['partner_id'],)).fetchone():
                problems.append({'id': merchant['id'], 'label': merchant['name'], 'message': 'Partenaire associé introuvable.'})
            value = body(merchant)
            if value or not merchant['hide_if_empty']:
                content += ('\n\n' if content else '') + '\n'.join(x for x in [merchant['heading'], value] if x)
        value = '\n'.join(x for x in [section['heading'], content] if x)
        initial[section['id']] = value
        if content or not section['hide_if_empty']:
            start = len('\n\n'.join(output)) + (2 if output else 0)
            anchors.append({'id': section['id'], 'start': start, 'end': start+len(value)})
            output.append(value)
    return {'text': '\n\n'.join(output), 'sections': anchors, 'problems': problems, 'initial_sections': initial}


def create_draft(db, data, origin):
    template = get(db, TABLES[0], data.get('template_id'))
    if type(data.get('template_revision')) is not int or data['template_revision'] != template['revision']:
        raise Conflict('Le modèle a changé. Rechargez-le avant de créer le brouillon.')
    snapshot = validate_template(template)
    prepared = render(db, snapshot, origin)
    return insert(db, TABLES[1], {'title': text(data, 'title', 160, True), 'template_id': template['id'],
        'template_revision': template['revision'], 'template_snapshot': snapshot, 'text': prepared['text'],
        'sections': prepared['sections'], 'products': [], 'selections': {}, 'manual_order': [],
        'problems': prepared['problems'], 'status': 'draft', 'youtube_url': '',
        'initial_sections': prepared['initial_sections']})


def editor_document(document):
    """Upgrade a phase-1 payload in memory, without consulting the mutable catalogue.

    Offsets on the wire and in SQLite are Unicode code points, never UTF-16 units.
    The initial rendered strings freeze the permanent URLs as well as the wording.
    """
    result = copy.deepcopy(document)
    anchors = {item['id']: item for item in result['sections']}
    initial = result.setdefault('initial_sections', {})
    normalized = []
    for section in result['template_snapshot']['sections']:
        key = section['id']
        anchor = anchors.get(key)
        if key not in initial:
            # Existing phase-1 drafts have not been edited through an editor yet.
            # Never render their bindings against today's catalogue as a migration.
            initial[key] = (result['text'][anchor['start']:anchor['end']] if anchor and anchor.get('start') is not None
                            else '\n'.join(x for x in (section['heading'], section['text'], section.get('after_text','')) if x))
        if anchor:
            anchor.setdefault('status', 'confirmed')
            anchor.setdefault('quote', result['text'][anchor['start']:anchor['end']] if anchor['status']=='confirmed' else '')
            anchor.setdefault('candidates', [])
        else:
            anchor = {'id': key, 'status': 'ambiguous', 'start': None, 'end': None, 'quote': '', 'candidates': []}
        normalized.append(anchor)
    result['sections'] = normalized
    result['editor_version'] = 1
    return result


def validate_anchors(items, content, definitions):
    allowed = {section['id'] for section in definitions}
    seen, intervals = set(), []
    for anchor in sequence(items, 50):
        if set(anchor) != {'id','status','start','end','quote','candidates'} or anchor['id'] not in allowed or anchor['id'] in seen:
            raise ValueError('Association de section invalide.')
        seen.add(anchor['id'])
        text(anchor, 'quote', MAX_TEXT)
        def span(value):
            start, end = value.get('start'), value.get('end')
            if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(content):
                raise ValueError('Position de section invalide (points de code Unicode requis).')
            return start, end
        if anchor['status'] == 'confirmed':
            start, end = span(anchor)
            if content[start:end] != anchor['quote']:raise ValueError('Le texte de la section a changé.')
            if end > start:intervals.append((start,end))
            if anchor['candidates']:raise ValueError('Une section confirmée ne doit pas contenir de propositions.')
        elif anchor['status'] == 'ambiguous':
            if anchor['start'] is not None or anchor['end'] is not None:raise ValueError('Position ambiguë non confirmée.')
        else:raise ValueError('État de section invalide.')
        for candidate in sequence(anchor['candidates'], 20):
            if set(candidate) != {'start','end'}:raise ValueError('Proposition de section invalide.')
            span(candidate)
    if seen != allowed:raise ValueError('Toutes les associations de sections doivent être conservées.')
    intervals.sort()
    if any(left[1] > right[0] for left,right in zip(intervals,intervals[1:])):
        raise ValueError('Des sections se chevauchent. Confirmez leurs emplacements.')
    return copy.deepcopy(items)


def save_draft(db, key, data, fork=False):
    current = editor_document(get(db, TABLES[1], key))
    if current['status'] != 'draft':raise ValueError('Ouvrez une copie brouillon pour modifier cette description.')
    mutation = ident(data.get('mutation_id'))
    expected = data.get('expected_revision')
    if type(expected) is not int or expected < 1:raise ValueError('Révision attendue requise.')
    base_fields = {'title','text','sections','expected_revision','mutation_id'}
    analysis_fields = {'analysis_version','products','selections','manual_order'}
    if set(data) not in (base_fields, base_fields | analysis_fields, base_fields | {'youtube_url'},base_fields | analysis_fields | {'youtube_url'}):
        raise ValueError('Champs de brouillon invalides.')
    content = text(data, 'text', MAX_TEXT)
    fields = {'title': text(data,'title',160,True), 'text': content,
              'sections': validate_anchors(data.get('sections'), content, current['template_snapshot']['sections'])}
    if 'analysis_version' in data:fields.update(validate_choices(data))
    if 'youtube_url' in data:
        from description_analysis import kind
        url=text(data,'youtube_url',2000)
        if url and (not affiliate_partners.http_url(url) or kind(url)!='youtube'):raise ValueError('URL YouTube HTTP(S) valide requise.')
        fields['youtube_url']=url
    digest = hashlib.sha256(packed(fields).encode('utf-8')).hexdigest()
    receipt = {'id': mutation, 'base_revision': expected, 'digest': digest}
    if fork:
        target = uuid.uuid5(uuid.NAMESPACE_URL, 'links:draft-copy:'+key+':'+mutation).hex
        previous = db.execute('SELECT * FROM description_drafts WHERE id=?', (target,)).fetchone()
        if previous:
            saved = decode(previous)
            if saved.get('last_mutation') != receipt:raise Conflict('Cette copie a déjà été enregistrée avec un autre contenu.')
            return saved
    elif current.get('last_mutation', {}).get('id') == mutation:
        if current['last_mutation'] != receipt:raise Conflict('Identifiant d’enregistrement déjà utilisé pour un autre contenu.')
        return current
    elif expected != current['revision']:
        raise Conflict('Le brouillon a changé dans un autre onglet. Votre texte est conservé ; comparez ou enregistrez une copie.')
    payload = validate_document({**current, **fields, 'last_mutation': receipt})
    return insert(db, TABLES[1], payload, target) if fork else update(db,TABLES[1],key,payload,expected)


def validate_choices(data):
    if type(data.get('analysis_version')) is not int or data['analysis_version'] != 1:raise ValueError('Version d’analyse invalide.')
    products=sequence(data.get('products'),100)
    seen=set()
    for product in products:
        if product.get('kind')!='manual-reference':continue  # Preserve earlier/future opaque product state.
        key=ident(product.get('id'))
        if key in seen:raise ValueError('Référence manuelle répétée.')
        seen.add(key);text(product,'query',160,True)
        if set(product)!={'id','kind','query'}:raise ValueError('Référence manuelle invalide.')
    selections=data.get('selections')
    if not isinstance(selections,dict):raise ValueError('Sélections invalides.')
    if 'merchant_search' in selections:
        from description_search import validate_state
        validate_state(selections['merchant_search'])
    if 'operations' in selections:
        from description_workflow import validate_options
        validate_options(selections['operations'])
    choices=selections.get('description_analysis',{})
    if not isinstance(choices,dict) or len(choices)>1000:raise ValueError('Trop de sélections.')
    for key,value in choices.items():
        ident(key)
        if not isinstance(value,dict) or set(value)-{'selected','link_id','source_id','label','product_id'}:raise ValueError('Choix invalide.')
        if 'selected' in value:flag(value,'selected')
        if 'label' in value:text(value,'label',160)
        for field in ('link_id','source_id','product_id'):
            if value.get(field):ident(value[field])
            elif field in value and value[field]!='':raise ValueError('Association invalide.')
    order=data.get('manual_order')
    if not isinstance(order,list) or len(order)>1000 or len(set(order))!=len(order):raise ValueError('Classement invalide.')
    for key in order:ident(key)
    return copy.deepcopy({key:data[key] for key in ('analysis_version','products','selections','manual_order')})


def analyze_draft(db,key,data,origin):
    from description_analysis import analyze
    if not isinstance(data,dict):raise ValueError('Requête d’analyse invalide.')
    current=editor_document(get(db,TABLES[1],key))
    content=text(data,'text',MAX_TEXT)
    anchors=validate_anchors(data.get('sections'),content,current['template_snapshot']['sections'])
    choices=validate_choices(data) if 'analysis_version' in data else {key:current[key] for key in ('products','selections','manual_order')}
    return analyze(db,{**current,**choices,'text':content,'sections':anchors},origin)


def validate_document(data, version=False):
    if not isinstance(data, dict):
        raise ValueError('Description invalide.')
    result = copy.deepcopy(data)
    for key in ('id', 'revision', 'created_at', 'updated_at', 'deleted'):
        result.pop(key, None)
    text(result, 'title', 160, True)
    text(result, 'text', MAX_TEXT)
    ident(result.get('template_id'))
    if type(result.get('template_revision')) is not int or result['template_revision'] < 1:
        raise ValueError('Révision du modèle invalide.')
    result['template_snapshot'] = validate_template(result.get('template_snapshot'))
    for key in ('sections', 'products', 'manual_order', 'problems'):
        if not isinstance(result.get(key), list):raise ValueError('État de description invalide : '+key)
    if not isinstance(result.get('selections'), dict) or result.get('status') not in {'draft', 'finalized'}:
        raise ValueError('État de description invalide.')
    if 'initial_sections' in result:
        initial = result['initial_sections']
        expected_ids = {s['id'] for s in result['template_snapshot']['sections']}
        if not isinstance(initial,dict) or set(initial) != expected_ids:raise ValueError('Copie initiale des sections invalide.')
        for key in initial:text(initial,key,MAX_TEXT)
    if 'editor_version' in result:
        if result['editor_version'] != 1:raise ValueError('Version d’éditeur incompatible.')
        validate_anchors(result['sections'],result['text'],result['template_snapshot']['sections'])
    if 'analysis_version' in result:validate_choices(result)
    url = text(result, 'youtube_url', 2000)
    if url and not affiliate_partners.http_url(url):raise ValueError('URL de vidéo invalide.')
    if version:
        if result['status'] != 'finalized':raise ValueError('État de version finalisée invalide.')
        ident(result.get('description_id'))
        datetime.fromisoformat(text(result, 'finalized_at', 80, True).replace('Z','+00:00'))
        if not isinstance(result.get('links'), list):raise ValueError('Liens de version invalides.')
    if len(packed(result)) > 1000000:raise ValueError('Description trop volumineuse.')
    return result


def export_backup(db):
    return {'version': 1, 'tables': {table: [dict(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY id')] for table in TABLES}}


def restore_backup(db, data):
    # Optional envelope, like affiliation: old backups leave this whole domain untouched.
    if data is None:return {'added': 0, 'retained': 0, 'conflicts': 0, 'recovered': 0}
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('tables'), dict) or set(data['tables']) != set(TABLES):
        raise ValueError('Sauvegarde Descriptions incomplète ou incompatible.')
    initialize(db, seed=False)  # Legacy empty receivers may predate this schema.
    result = {'added': 0, 'retained': 0, 'conflicts': 0, 'recovered': 0}
    for table in TABLES:
        seen = set()
        for row in sequence(data['tables'][table], 500000):
            if set(row) != {'id', 'revision', 'payload', 'created_at', 'updated_at', 'deleted'}:
                raise ValueError('Enregistrement Descriptions invalide.')
            key = ident(row['id'])
            if key in seen:raise ValueError('Identifiant Descriptions répété.')
            seen.add(key)
            if type(row['revision']) is not int or row['revision'] < 1 or type(row['deleted']) is not int or row['deleted'] not in (0,1):
                raise ValueError('Révision Descriptions invalide.')
            for field in ('created_at','updated_at'):
                datetime.fromisoformat(text(row, field, 80, True).replace('Z','+00:00'))
            payload = json.loads(text(row, 'payload', 1000000, True))
            validated = validate_template(payload) if table == TABLES[0] else validate_document(payload, table == TABLES[2])
            if payload != validated:raise ValueError('Contenu Descriptions invalide.')
            current = db.execute('SELECT * FROM '+table+' WHERE id=?', (key,)).fetchone()
            if current:
                # Restoring a snapshot cannot clobber an open editor, resurrect a deleted
                # template, or rewrite a finalized version. Differences are reported.
                conflict = json.loads(current['payload']) != payload or current['deleted'] != row['deleted']
                if conflict and table == TABLES[2]:raise ValueError('Conflit avec une version finalisée immuable.')
                result['retained'] += 1
                result['conflicts'] += int(conflict)
                if conflict and not row['deleted']:
                    # Preserve both edits, idempotently. The original identity and revision
                    # stay untouched so another tab cannot overwrite a restored object.
                    recovered_id = uuid.uuid5(uuid.NAMESPACE_URL, 'links:description-recovery:'+table+':'+key+':'+packed(payload)).hex
                    if not db.execute('SELECT 1 FROM '+table+' WHERE id=?', (recovered_id,)).fetchone():
                        recovered = copy.deepcopy(payload)
                        field = 'name' if table == TABLES[0] else 'title'
                        recovered[field] = recovered[field][:130]+' — restauré'
                        insert(db, table, recovered, recovered_id)
                        result['recovered'] += 1
            else:
                db.execute('INSERT INTO '+table+' VALUES(?,?,?,?,?,?)', tuple(row[k] for k in ('id','revision','payload','created_at','updated_at','deleted')))
                result['added'] += 1
    return result


def read(db, path, origin):
    match = re.fullmatch(r'drafts/([\w-]+)/versions', path)
    if match:return {'items':[v for v in rows(db,TABLES[2]) if v['description_id']==match[1]]}
    match = re.fullmatch(r'versions/([\w-]+)', path)
    if match:return {'version':get(db,TABLES[2],match[1])}
    if path == 'templates':return {'items': rows(db, TABLES[0])}
    if path == 'catalogue':return catalogue(db)
    if path == 'drafts':return {'items': rows(db, TABLES[1])}
    match = re.fullmatch(r'drafts/([\w-]+)', path)
    if match:
        instance = db.execute("SELECT value FROM settings WHERE key='app.instance_id'").fetchone()
        return {'document': editor_document(get(db,TABLES[1],match[1])), 'instance_id': instance[0] if instance else ''}
    match = re.fullmatch(r'templates/([\w-]+)/preview', path)
    if match:return render(db, get(db, TABLES[0], match[1]), origin)
    raise ValueError('Ressource Descriptions inconnue.')


def write(db, path, data, origin, url_valid=affiliate_partners.http_url):
    if not isinstance(data, dict):raise ValueError('Requête invalide.')
    match = re.fullmatch(r'drafts/([\w-]+)/(apply|finalize)',path)
    if match:
        import description_workflow as workflow
        if match[2]=='apply':return workflow.apply(db,match[1],data,origin,url_valid)
        return workflow.finalize(db,match[1],data,origin)
    match = re.fullmatch(r'versions/([\w-]+)/restore',path)
    if match:
        from description_workflow import restore
        return restore(db,match[1],data)
    if path == 'templates':return insert(db, TABLES[0], validate_template(data))
    if path == 'preview':return render(db, validate_template(data), origin)
    if path == 'drafts':return create_draft(db, data, origin)
    match = re.fullmatch(r'drafts/([\w-]+)/(save|fork)', path)
    if match:return save_draft(db,match[1],data,match[2]=='fork')
    match = re.fullmatch(r'templates/([\w-]+)/(save|duplicate|delete)', path)
    if match:
        key, action = match.groups()
        current = get(db, TABLES[0], key)
        if type(data.get('expected_revision')) is not int or data['expected_revision'] != current['revision']:
            raise Conflict('Le modèle a changé ailleurs. Votre saisie est conservée ; rechargez avant de réessayer.')
        if action == 'duplicate':
            payload = validate_template(current)
            payload['name'] = text(data, 'name', 160, True)
            return insert(db, TABLES[0], payload)
        payload = validate_template(data) if action == 'save' else validate_template(current)
        return update(db, TABLES[0], key, payload, data.get('expected_revision'), action == 'delete')
    raise ValueError('Action Descriptions inconnue.')
