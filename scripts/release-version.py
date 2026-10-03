"""Persist one production version per validated source commit; retries reuse it."""
import json, os, re, subprocess
from pathlib import Path

def validate(value):
    if not isinstance(value,str) or not re.fullmatch(r"V[0-9]+\.[0-9]+",value) or len(value)>40:raise ValueError("Invalid application version")
    return value

def next_version(value,minor=False):
    major,number=validate(value)[1:].split('.')
    feature,patch=(int(number[:-2]),int(number[-2:])) if len(number)>=3 else (int(number),0)
    if minor:return f'V{major}.{feature+1}'
    if patch==99:raise ValueError('99 corrections reached; select an explicit milestone')
    return f'V{major}.{feature}{patch+1:02d}'

def choose(message,official=False,override='',current=None):
    pinned=re.match(r'^Release (V[0-9]+\.[0-9]+)(?:\s|$)',message)
    if override:return validate(override)
    if pinned:return validate(pinned.group(1))
    current=current or (Path(__file__).resolve().parent.parent/'VERSION').read_text().strip()
    return next_version(current,minor=message.startswith('[release minor]'))

def plan(current,source,state=None,override=''):
    if state and state.get('source_sha')==source:
        version=validate(state['version'])
        if override and override!=version:raise ValueError('This source already has a reserved version')
        return version
    return validate(override) if override else next_version(current)

def reserve(root,source,override=''):
    path=root/'.release-state.json';state=json.loads(path.read_text()) if path.exists() else None
    current=(root/'VERSION').read_text().strip();version=plan(current,source,state,override)
    (root/'VERSION').write_text(version+'\n')
    path.write_text(json.dumps({'source_sha':source,'version':version},indent=2)+'\n')
    readme=root/'README.md'
    if readme.exists():readme.write_text(re.sub(r'Version du code : \*\*V[0-9]+\.[0-9]+\*\*',f'Version du code : **{version}**',readme.read_text()))
    return version

if __name__=='__main__':
    root=Path(__file__).resolve().parent.parent
    source=os.environ['GITHUB_SHA'];override=os.environ.get('RELEASE_OVERRIDE','')
    def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
    git('fetch','origin','main')
    tip=git('rev-parse','origin/main');state_path=root/'.release-state.json'
    remote_state=None
    try:remote_state=json.loads(git('show','origin/main:.release-state.json'))
    except (subprocess.CalledProcessError,ValueError):pass
    # Never publish a stale queued run or move latest backwards on a manual retry.
    eligible=tip==source or (remote_state and remote_state.get('source_sha')==source and git('rev-parse','origin/main^')==source)
    if eligible:
        git('checkout','--detach',tip)
        version=reserve(root,source,override)
        git('config','user.name','github-actions[bot]');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
        git('add','VERSION','.release-state.json',*(['README.md'] if (root/'README.md').exists() else []))
        if git('diff','--cached','--name-only'):
            git('commit','-m',f'Reserve production {version} [skip ci]');git('push','origin','HEAD:main')
        release_commit=git('rev-parse','HEAD')
    else:version='';release_commit=''
    with open(os.environ['GITHUB_OUTPUT'],'a') as output:output.write(f'version={version}\ntag={version.lower()}\neligible={str(bool(eligible)).lower()}\ncommit={release_commit}\n')
