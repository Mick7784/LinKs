"""Run with Python inside the OLD image before upgrading. No network or secrets."""
import argparse, ast, json, os, shutil, sqlite3
from pathlib import Path
from urllib.parse import urlsplit

def preserve(root,data_dir):
    root=Path(root);data=Path(data_dir);data.mkdir(parents=True,exist_ok=True)
    destination=data/'legacy-instance.json'
    if destination.exists():raise SystemExit('Transfert déjà présent : conserver ce fichier et sa sauvegarde.')
    config_path=root/'links.json'
    config=json.loads(config_path.read_text())
    public=Path('/usr/share/nginx/html') if Path('/usr/share/nginx/html').exists() else root/'site'
    assets=public/'assets';target=data/'assets';target.mkdir(exist_ok=True)
    for path in assets.iterdir():
        if path.is_file():
            dest=target/path.name
            if dest.exists() and dest.read_bytes()!=path.read_bytes():raise SystemExit('Asset existant différent : '+path.name)
            if not dest.exists():shutil.copy2(path,dest)
    aliases={}
    for collection,prefix,idprefix,label in [('links','block:','legacy-link-','title'),('socials','button:','legacy-button-','label')]:
        candidates={}
        for i,item in enumerate(config.get(collection,[])):
            name=item.get(label,item.get('platform',''))
            if name:candidates.setdefault(('Réseau · ' if collection=='socials' else '')+name,[]).append(prefix+idprefix+str(i))
        aliases.update({k:v[0] for k,v in candidates.items() if len(v)==1})
    script=root/'analytics.py'
    if not script.exists():script=root/'scripts'/'analytics.py'
    tree=ast.parse(script.read_text());source=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='source_of')
    generic={'youtube','instagram','facebook','tiktok','discord','google','newsletter'}
    rules={};alias_map={}
    for node in ast.walk(source):
        if isinstance(node,ast.Dict):
            try:alias_map.update(ast.literal_eval(node))
            except (ValueError,TypeError):pass
        if isinstance(node,ast.List):
            try:pairs=ast.literal_eval(node)
            except (ValueError,TypeError):continue
            for domain,name in pairs:
                if name not in generic:rules.setdefault(name,{'key':name,'label':config.get('profile',{}).get('name',name),'aliases':[],'domains':[]})['domains'].append(domain)
    for alias,key in alias_map.items():
        if key in rules and alias!=key:rules[key]['aliases'].append(alias)
    origin=os.environ.get('ANALYTICS_ORIGIN') or config.get('siteUrl','')
    if not origin:raise SystemExit('Adresse publique absente : transfert refusé.')
    manifest={'config':config,'site_url':origin,'timezone':'Europe/Paris','source_rules':list(rules.values()),'metric_aliases':aliases,'analytics_enabled':os.environ.get('ANALYTICS_ENABLED','true')}
    backup=data/'pre-v11-volume';backup.mkdir(exist_ok=True)
    database=Path(os.environ.get('ANALYTICS_DB',str(data/'analytics.db')))
    if database.exists():
        with sqlite3.connect(database) as db,sqlite3.connect(backup/'analytics.db') as copy:db.backup(copy)
    uploads=Path(os.environ.get('UPLOAD_DIR',str(data/'uploads')))
    if uploads.exists():shutil.copytree(uploads,backup/'uploads',dirs_exist_ok=True)
    shutil.copytree(target,backup/'assets',dirs_exist_ok=True)
    temp=destination.with_suffix('.tmp');temp.write_text(json.dumps(manifest,ensure_ascii=False));temp.chmod(0o600);temp.replace(destination)
    print('Transfert historique conservé dans le stockage persistant. Conserver aussi une sauvegarde externe du volume.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',default='/app');parser.add_argument('--data',default='/data');args=parser.parse_args();preserve(args.root,args.data)
