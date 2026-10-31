"""Human-readable release notes and changelog share the same source."""
import re, subprocess
from pathlib import Path

SECTIONS=[('feat','✨ Nouveautés'),('ui','🎨 Interface'),('theme','🎨 Thèmes / Apparence'),('improve','🔧 Améliorations'),('fix','🐛 Corrections'),('perf','⚡ Performance'),('tech','⚙️ Technique'),('update','⬆️ Mise à jour'),('breaking','⚠️ Compatibilité / Breaking changes')]

def render(commits):
    groups={key:[] for key,_ in SECTIONS}
    for subject in commits:
        if subject.startswith(('Reserve production','Merge ','Merge pull request')):continue
        match=re.match(r'^(feat|ui|theme|improve|fix|perf|tech|update|breaking)(?:\([^)]*\))?(!)?:\s*(.+)',subject)
        if match:key,text=('breaking' if match[2] else match[1]),match[3]
        else:key,text='improve',subject
        if text and text not in groups[key]:groups[key].append(text)
    return '\n\n'.join('## '+label+'\n\n'+'\n'.join('- '+text for text in groups[key]) for key,label in SECTIONS if groups[key])+'\n'

def prepare(root,version,source):
    notes=root/'docs'/'releases'/(version+'.md')
    if not notes.exists():
        def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
        tags=git('tag','--merged',source,'--sort=-creatordate').splitlines()
        previous=next((tag for tag in tags if re.fullmatch(r'[Vv]\d+\.\d+(?:\.\d+)?',tag)),None)
        subjects=git('log','--format=%s',(previous+'..'+source) if previous else source).splitlines()
        text=render(subjects)
        if not text.strip():raise ValueError('Release notes manquantes')
        notes.parent.mkdir(parents=True,exist_ok=True);notes.write_text(text,encoding='utf-8')
    text=notes.read_text(encoding='utf-8').strip()
    if not text or not re.search(r'^## .+',text,re.M):raise ValueError('Release notes structurées requises')
    changelog=root/'CHANGELOG.md';old=changelog.read_text(encoding='utf-8') if changelog.exists() else '# Changelog\n\n'
    heading='## '+version
    if not re.search(r'^'+re.escape(heading)+r'$',old,re.M):
        # Notes use third-level headings inside the changelog.
        entry=heading+'\n\n'+re.sub(r'^## ',r'### ',text,flags=re.M)+'\n\n'
        changelog.write_text('# Changelog\n\n'+entry+re.sub(r'^# Changelog\s*','',old),encoding='utf-8')
    return notes
