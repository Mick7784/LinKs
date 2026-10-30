"""Safely preview and create tracked links in batches, without publication sources.

The existing single-link partner resolver, duplicate checks, and save path remain
authoritative. A batch is atomic: no link is saved if any selected entry is stale,
invalid or duplicates another selected/existing destination.
"""
import affiliate_partners
import tracked_links

MAX_BATCH = 50


def _items(data):
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError('Liste d’URL invalide.')
    items = data['items']
    if not 1 <= len(items) <= MAX_BATCH:
        raise ValueError('Saisissez entre 1 et 50 liens.')
    if any(not isinstance(item, dict) for item in items):
        raise ValueError('Chaque ligne doit contenir une URL.')
    return items


def _preview_fields(item):
    url = tracked_links.text_field(item, 'url', 2000, True)
    if item.get('manual_partner') is True:
        partner_id = tracked_links.text_field(item, 'partner_id', 32)
        return {'url': url, 'partner_id': partner_id, 'apply_partner': True}
    if item.get('manual_partner') not in (None, False):
        raise ValueError('Choix du partenaire invalide.')
    return {'url': url, 'detect': True, 'apply_partner': True}


def preview_many(db, data, url_valid):
    """Read-only row-by-row preview; malformed rows do not abort other previews."""
    items = _items(data)
    result = []
    found = {}
    for index, item in enumerate(items):
        try:
            preview = affiliate_partners.preview_tracked(db, _preview_fields(item), url_valid=url_valid)
            key = tracked_links.canonical_destination(preview['url'])
            earlier = found.get(key)
            if earlier is None:
                found[key] = index
            result.append({
                'index': index,
                'original_url': preview['original_url'],
                'final_url': preview['url'],
                'partner_id': preview['partner_id'],
                'duplicates': [{
                    'id': row['id'], 'name': row['name'],
                    'archived': bool(row['archived']), 'enabled': bool(row['enabled'])
                } for row in preview['duplicates']],
                'duplicate_of': earlier,
                'error': '',
            })
        except (ValueError, UnicodeError) as exc:
            result.append({'index': index, 'error': str(exc) or 'URL invalide.'})
    return {'items': result}


def create_many(db, data, url_valid, now):
    """Caller must hold BEGIN IMMEDIATE: validate everything, then save everything."""
    items = _items(data)
    pending = []
    seen = set()
    for item in items:
        name = tracked_links.text_field(item, 'name', 160, True)
        url = tracked_links.text_field(item, 'url', 2000, True)
        if 'partner_id' not in item:
            raise ValueError('Le partenaire doit être confirmé dans l’aperçu.')
        partner_id = tracked_links.text_field(item, 'partner_id', 32)
        expected_url = tracked_links.text_field(item, 'expected_url', 2000, True)
        fields = {
            'name': name, 'url': url, 'partner_id': partner_id,
            'apply_partner': True, 'expected_url': expected_url,
            'notes': '',
        }
        preview = affiliate_partners.preview_tracked(db, fields, url_valid=url_valid)
        affiliate_partners.confirm_preview(fields, preview)
        if preview['duplicates']:
            raise tracked_links.DuplicateDestination(preview['duplicates'])
        key = tracked_links.canonical_destination(preview['url'])
        if key in seen:
            raise ValueError('Deux lignes du lot produisent la même destination. Supprimez le doublon.')
        seen.add(key)
        pending.append(fields)

    created = [affiliate_partners.save_tracked(db, fields, url_valid, now)
               for fields in pending]
    return {'created': len(created), 'items': [
        {'id': row['id'], 'name': row['name'], 'url': row['url']}
        for row in created
    ]}
