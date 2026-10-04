"""Reference-aware trash for user uploads only. Call under the data lock."""
import json
import re
import time
from pathlib import Path

NAME = re.compile(r'[a-f0-9-]{36}\.(png|jpg|webp|gif)')
GRACE_SECONDS = 7 * 24 * 60 * 60


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS upload_trash(name TEXT PRIMARY KEY, orphaned_at REAL NOT NULL)')


def references(db):
    refs = {}
    def add(value, label):
        if isinstance(value, str) and value.startswith('/uploads/') and NAME.fullmatch(value[9:]):
            refs.setdefault(value[9:], []).append(label)
    for row in db.execute('SELECT image,internal_name,archived FROM content_blocks'):
        add(row['image'], row['internal_name'] + (' (archivé)' if row['archived'] else ''))
    for row in db.execute('SELECT custom_icon,label FROM top_buttons'):
        add(row['custom_icon'], 'Raccourci : ' + row['label'])
    values = {row['key']: row['value'] for row in db.execute('SELECT key,value FROM settings')}
    for key, label in [('profile.logo', 'Logo'), ('profile.avatar', 'Avatar')]:
        add(values.get(key), label)
    for theme in json.loads(values.get('appearance.themes', '[]')):
        for value in theme.get('tokens', {}).values():
            add(value, 'Thème : ' + theme['name'])
    return refs


def require_file(uploads, ref, db=None):
    if ref and ref.startswith('/uploads/'):
        name = ref[9:]
        if not NAME.fullmatch(name) or not (uploads / name).is_file() or (uploads / name).is_symlink():
            raise ValueError('Image personnelle introuvable : importer de nouveau le fichier')
        if db is not None:
            # Cancellation shares the transaction attaching the file to its new owner.
            db.execute('DELETE FROM upload_trash WHERE name=?', (name,))


def scan(db, uploads, action='scan', now=None):
    if action not in {'scan', 'cleanup', 'empty'}:
        raise ValueError('Action de stockage inconnue')
    now = time.time() if now is None else now
    refs = references(db)
    files = {p.name: p for p in uploads.iterdir() if NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()}
    for name in [row[0] for row in db.execute('SELECT name FROM upload_trash')]:
        if name in refs or name not in files:
            db.execute('DELETE FROM upload_trash WHERE name=?', (name,))
    for name in files.keys() - refs.keys():
        # Never infer orphan age from mtime: historical untracked files get a full grace period.
        db.execute('INSERT OR IGNORE INTO upload_trash VALUES(?,?)', (name, now))
    trash = {row[0]: row[1] for row in db.execute('SELECT name,orphaned_at FROM upload_trash')}
    deleted = 0
    for name, orphaned_at in list(trash.items()):
        if action != 'empty' and now - orphaned_at < GRACE_SECONDS:
            continue
        # Recheck all content, including inactive/archived and non-active themes, before unlink.
        if name in references(db):
            db.execute('DELETE FROM upload_trash WHERE name=?', (name,))
            continue
        try:
            files[name].unlink()
        except OSError:
            continue
        db.execute('DELETE FROM upload_trash WHERE name=?', (name,))
        del files[name]
        del trash[name]
        deleted += 1
    items = []
    for name, path in sorted(files.items()):
        uses = refs.get(name, [])
        items.append({'name': name, 'url': '/uploads/' + name, 'size': path.stat().st_size,
                      'type': path.suffix[1:].upper(), 'uses': uses, 'orphaned_at': trash.get(name),
                      'delete_at': trash[name] + GRACE_SECONDS if name in trash else None})
    return {'items': items, 'bytes': sum(x['size'] for x in items),
            'used': sum(bool(x['uses']) for x in items), 'unused': sum(not x['uses'] for x in items),
            'grace_days': GRACE_SECONDS // 86400, 'deleted': deleted}
