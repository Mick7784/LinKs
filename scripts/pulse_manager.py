"""Narrow PulSe adapter over the existing LinKs engine; no storage or URL rules here."""
import hashlib
import hmac
import json
import os
import time
import affiliate_partners as partners
import tracked_links as links


class Conflict(ValueError):
    pass


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def item(db, ident):
    if not isinstance(ident, str) or not links.IDENT.fullmatch(ident):
        raise ValueError('Identifiant de lien invalide.')
    row = db.execute('SELECT * FROM tracked_links WHERE id=?', (ident,)).fetchone()
    if not row or row['archived'] or not row['enabled']:
        raise ValueError('Lien indisponible. Vérifiez son état dans LinKs.')
    value = {key: row[key] for key in ('id', 'name', 'url', 'notes', 'updated_at')}
    value.update(partners.link_metadata(db, ident, row['url']))
    value['revision'] = hashlib.sha256(packed(value)).hexdigest()
    return value


def catalog(a):
    with a.connection() as db:
        return {'version': 1,
                'items': [item(db, row['id']) for row in links.list_links(db) if row['enabled'] and not row['archived']],
                'partners': [{key: row[key] for key in ('id', 'name')} for row in partners.rows(db)],
                'sources': [{key: row[key] for key in ('id', 'name', 'platform', 'historical')} for row in links.source_rows(db) if row['active']]}


def fields(data):
    # partner_id is mandatory: never enter the engine's legacy direct-write path.
    if 'partner_id' not in data:
        raise ValueError('Choix du partenaire requis.')
    return {**{key: links.text_field(data, key, limit, required) for key, limit, required in
               [('name', 160, True), ('url', 2000, True), ('notes', 800, False), ('partner_id', 32, False)]},
            'apply_partner': data.get('apply_partner') is True}


def checked_current(db, data):
    ident = data.get('id', '')
    if not ident:
        return None
    current = item(db, ident)
    if data.get('revision') != current['revision']:
        raise Conflict('Ce lien a changé dans LinKs. Rouvrez-le avant de modifier sa destination.')
    return current


def proof(data):
    # Domain-separated receipt: confirms that this exact form was previewed.
    value = {key: data.get(key) for key in ('id', 'revision', 'name', 'url', 'notes', 'partner_id',
             'apply_partner', 'expected_url', 'previous_url', 'expires')}
    return hmac.new(os.environ['PULSE_BRIDGE_TOKEN'].encode(), b'pulse-link-preview-v1\0'+packed(value), hashlib.sha256).hexdigest()


def preview(a, data):
    form = fields(data)
    with a.connection() as db:
        current = checked_current(db, data)
        result = partners.preview_tracked(db, {**form, 'detect': data.get('detect') is True}, current['id'] if current else None, a.story_url_valid)
        form['partner_id'] = result['partner_id']
        receipt = {**form, 'id': current['id'] if current else '', 'revision': current['revision'] if current else '',
                   'expected_url': result['url'], 'previous_url': result['previous_url'], 'expires': int(time.time())+600}
        return {'preview': result, 'receipt': {**receipt, 'proof': proof(receipt)}}


def save(a, data):
    form = fields(data)
    expires = data.get('expires')
    if (type(expires) is not int or not int(time.time()) <= expires <= int(time.time())+600
            or not isinstance(data.get('proof'), str) or not hmac.compare_digest(proof({**data, **form}), data['proof'])):
        raise Conflict('Vérifiez à nouveau l’URL finale avant d’enregistrer (aperçu expiré ou modifié).')
    with a.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = checked_current(db, data)
        # No duplicate override from PulSe. The common engine rechecks under lock.
        saved = partners.save_tracked(db, {**form, 'expected_url': data.get('expected_url'),
                    'previous_url': data.get('previous_url'), 'confirm_destination': data.get('confirm_destination') is True},
                    a.story_url_valid, a.now_iso(), current['id'] if current else None)
        result = item(db, saved['id'])
    return {'item': result}


def token(a, data):
    with a.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = item(db, data.get('id'))
        if data.get('expected_url') != current['url']:
            raise Conflict('La destination a changé. Vérifiez le lien avant de le partager.')
        result = links.token_link(db, current['id'], data.get('source_id'), a.ORIGIN, a.now_iso())
    return {key: result[key] for key in ('url', 'source_id')}
