"""User file inventory and reference-aware trash. Call under the data lock.

Only the writable user directories are inventoried, never bundled system assets.
The old upload_trash keys are retained for additive V1.302 compatibility.
"""
import json
import re
import time
import uuid
import filecmp
from pathlib import Path

NAME = re.compile(r'[a-f0-9-]{36}\.(png|jpg|webp|gif)')
ASSET_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*')
GRACE_SECONDS = 7 * 24 * 60 * 60


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS upload_trash(name TEXT PRIMARY KEY, orphaned_at REAL NOT NULL)')
    db.execute("CREATE TABLE IF NOT EXISTS user_files(name TEXT PRIMARY KEY, created_at REAL NOT NULL, category TEXT NOT NULL DEFAULT 'other')")
    if 'category' not in {row[1] for row in db.execute('PRAGMA table_info(user_files)')}:
        db.execute("ALTER TABLE user_files ADD COLUMN category TEXT NOT NULL DEFAULT 'other'")


def file_key(value):
    if not isinstance(value, str):return None
    if value.startswith('/uploads/') and NAME.fullmatch(value[9:]):return value[9:]
    if value.startswith('/assets/') and ASSET_NAME.fullmatch(value[8:]):return 'assets/' + value[8:]
    return None


def write(path, raw):
    """Atomic file writes shared by uploads, setup, imports and restoration."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + str(uuid.uuid4()) + '.tmp')
    try:
        temporary.write_bytes(raw)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def summary(db, uploads, assets):
    """Small overview: reuse the registered inventory without building owner/file lists."""
    result={'bytes':0,'trash_bytes':0,'unused':0}
    trash={row[0] for row in db.execute('SELECT name FROM upload_trash')}
    for row in db.execute('SELECT name FROM user_files'):
        key=row[0]
        if not file_key('/'+key if key.startswith('assets/') else '/uploads/'+key):continue
        path=assets/key[7:] if key.startswith('assets/') else uploads/key
        if path.is_file() and not path.is_symlink():
            size=path.stat().st_size;result['bytes']+=size
            if key in trash:result['trash_bytes']+=size;result['unused']+=1
    return result


def references(db):
    refs = {}
    def add(value, label, category):
        key = file_key(value)
        if key:refs.setdefault(key, []).append({'label': label, 'category': category})
    for row in db.execute('SELECT image,internal_name,archived,type FROM content_blocks'):
        add(row['image'], row['internal_name'] + (' (archivé)' if row['archived'] else ''), 'campaigns' if row['type'] in {'promo','featured'} else 'links')
    for row in db.execute('SELECT custom_icon,label FROM top_buttons'):
        add(row['custom_icon'], 'Raccourci : ' + row['label'], 'icons')
    values = {row['key']: row['value'] for row in db.execute('SELECT key,value FROM settings')}
    for key, label in [('profile.logo', 'Logo'), ('profile.avatar', 'Avatar')]:
        add(values.get(key), label, 'profile')
    add(values.get('appearance.campaign_image'), 'Visuel par défaut des campagnes', 'campaigns')
    for theme in json.loads(values.get('appearance.themes', '[]')):
        for value in theme.get('tokens', {}).values():
            add(value, 'Thème : ' + theme['name'], 'themes')
    # Preserve future/legacy setting-owned files as well, without treating arbitrary
    # URLs or system: IDs as local files. Known references keep their precise category.
    def walk(value, label):
        if isinstance(value, dict):
            for key, child in value.items():walk(child, label + ' / ' + key)
        elif isinstance(value, list):
            for child in value:walk(child, label)
        elif file_key(value):add(value, label, 'other')
    for key, value in values.items():
        if key in {'profile.logo','profile.avatar','appearance.themes','appearance.campaign_image'}:continue
        try:walk(json.loads(value), key)
        except (ValueError, TypeError):walk(value, key)
    return refs


def require_file(uploads, ref, db=None, assets=None, system_assets=None):
    if ref and ref.startswith('/uploads/'):
        name = ref[9:]
        if not NAME.fullmatch(name) or not (uploads / name).is_file() or (uploads / name).is_symlink():
            raise ValueError('Image personnelle introuvable : importer de nouveau le fichier')
        if db is not None:
            # Cancellation shares the transaction attaching the file to its new owner.
            db.execute('DELETE FROM upload_trash WHERE name=?', (name,))
    elif ref and ref.startswith('/assets/'):
        key=file_key(ref)
        if not key:raise ValueError('Référence de fichier invalide')
        if assets is not None:
            path=assets/ref[8:]
            if not path.is_file() and system_assets is not None:path=system_assets/ref[8:]
            if not path.is_file() or path.is_symlink():raise ValueError('Image personnelle introuvable : importer de nouveau le fichier')
        if db is not None:db.execute('DELETE FROM upload_trash WHERE name=?', (key,))


def scan(db, uploads, action='scan', now=None, assets=None, system_assets=None):
    if action not in {'scan', 'cleanup', 'empty'}:
        raise ValueError('Action de stockage inconnue')
    now = time.time() if now is None else now
    refs = references(db)
    files = {p.name: p for p in uploads.iterdir() if NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()}
    if assets is not None and assets.is_dir() and not assets.is_symlink():
        files.update({'assets/' + p.name:p for p in assets.iterdir() if ASSET_NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()})
        # Historical migrations may copy bundled artwork into /data/assets.
        # Protect exact system copies; same-name user overrides remain managed.
        if system_assets is not None:
            files={key:path for key,path in files.items() if not (key.startswith('assets/') and (system_assets/path.name).is_file() and filecmp.cmp(path,system_assets/path.name,shallow=False))}
    dates = dict(db.execute('SELECT name,created_at FROM user_files'))
    previous_categories = dict(db.execute('SELECT name,category FROM user_files'))
    stats = {name:path.stat() for name,path in files.items()}
    for name in files.keys() - dates.keys():
        dates[name]=stats[name].st_mtime
        db.execute('INSERT INTO user_files(name,created_at) VALUES(?,?)', (name, dates[name]))
    for name in dates.keys() - files.keys():
        db.execute('DELETE FROM user_files WHERE name=?', (name,))
    for name in [row[0] for row in db.execute('SELECT name FROM upload_trash')]:
        if name in refs or name not in files:
            db.execute('DELETE FROM upload_trash WHERE name=?', (name,))
    for name in files.keys() - refs.keys():
        # Never infer orphan age from mtime: historical untracked files get a full grace period.
        db.execute('INSERT OR IGNORE INTO upload_trash VALUES(?,?)', (name, now))
    trash = {row[0]: row[1] for row in db.execute('SELECT name,orphaned_at FROM upload_trash')}
    deleted = 0
    # The data lock is held through this batch, so attaching transactions cannot
    # race with unlink. Recheck once before the batch, rather than N full DB scans.
    live_refs=references(db)
    for name, orphaned_at in list(trash.items()):
        if action != 'empty' and now - orphaned_at < GRACE_SECONDS:
            continue
        # Recheck all content, including inactive/archived and non-active themes, before unlink.
        if name in live_refs:
            db.execute('DELETE FROM upload_trash WHERE name=?', (name,))
            continue
        try:
            files[name].unlink()
        except OSError:
            continue
        db.execute('DELETE FROM upload_trash WHERE name=?', (name,))
        db.execute('DELETE FROM user_files WHERE name=?', (name,))
        del files[name]
        del trash[name]
        deleted += 1
    items = []
    for name, path in sorted(files.items()):
        owners = refs.get(name, [])
        categories = sorted({x['category'] for x in owners}) or [previous_categories.get(name,'other')]
        if owners and previous_categories.get(name,'other')!=categories[0]:
            db.execute('UPDATE user_files SET category=? WHERE name=?', (categories[0],name))
        items.append({'name': name, 'url': '/' + name if name.startswith('assets/') else '/uploads/' + name, 'size': stats[name].st_size,
                      'type': path.suffix[1:].upper() or 'FICHIER', 'uses': [x['label'] for x in owners], 'categories': categories,
                      'category': categories[0], 'created_at': dates[name], 'orphaned_at': trash.get(name),
                      'delete_at': trash[name] + GRACE_SECONDS if name in trash else None})
    # A shared file counts once in the breakdown; all its categories/owners remain visible.
    categories = {key:sum(x['size'] for x in items if x['category']==key) for key in ['campaigns','links','profile','themes','icons','other']}
    return {'items': items, 'bytes': sum(x['size'] for x in items), 'categories': categories,
            'trash_bytes':sum(x['size'] for x in items if not x['uses']),
            'used': sum(bool(x['uses']) for x in items), 'unused': sum(not x['uses'] for x in items),
            'grace_days': GRACE_SECONDS // 86400, 'deleted': deleted}
