"""Automatic archive decisions; uncertain evidence is retained outside financial totals."""
import copy
import csv
import hashlib
import json
from datetime import datetime
import amazon_affiliation as amazon

RANK={'category':0,'daily_trends':1,'tracking_id':2,'linked_product':3,'legacy':4}
ENGINE='archives-2'
STATES={'pending','unusable','complementary','active','replaced','ignored'}


def archives(db,identity):
    active_ids={r['id'] for r in amazon.active_reports(db,identity)}
    reports=[(r['id'],json.loads(r['summary']).get('amazon',{})) for r in db.execute('SELECT id,summary FROM aff_snapshots WHERE account_id=?',(identity,))]
    items=[]
    for row in db.execute('SELECT id,observed_at,summary FROM aff_snapshots WHERE account_id=? ORDER BY id DESC',(identity,)):
        value=json.loads(row['summary']).get('amazon_pending')
        if not value:continue
        state=value.get('state','pending')
        linked=[ident for ident,v in reports if v.get('archive_digest')==value['digest'] or ident in value.get('report_ids',[])]
        if state=='active' and linked and not active_ids.intersection(linked):state='replaced'
        items.append({'id':row['id'],'observed_at':row['observed_at'],**{k:v for k,v in value.items() if k not in {'archive','version','state'}},
            'state':state,'report_ids':linked,'can_reanalyze':state in {'pending','unusable','complementary','ignored'},'can_ignore':state in {'pending','unusable','complementary'}})
    return items

def fingerprint(value):
    keys=('kind','start','end','scope','currency','rows')
    return json.dumps({**{k:value[k] for k in keys},'view':value.get('view','legacy'),'date_basis':value.get('date_basis')},sort_keys=True)

def pending_reports(db,identity):
    return [{k:item for k,item in v.items() if k not in {'diagnostics','attempts'}} for v in archives(db,identity) if v['state'] in {'pending','unusable'}]

def validate_pending(value):
    required={'version','archive','digest','filename','reasons'}
    optional={'state','diagnostics','attempts','report_ids','engine'}
    if not isinstance(value,dict) or not required<=set(value) or set(value)-required-optional or value['version']!=1:
        raise ValueError('Archive en attente invalide.')
    if not isinstance(value['filename'],str) or len(value['filename'])>240 or not isinstance(value['reasons'],list) or not 1<=len(value['reasons'])<=64 or any(not isinstance(r,str) or len(r)>2000 for r in value['reasons']):
        raise ValueError('Diagnostic en attente invalide.')
    if amazon.inspect_archive(value)['digest']!=value['digest']:raise ValueError('Empreinte de l’archive invalide.')
    if value.get('state','pending') not in STATES:raise ValueError('État d’archive invalide.')
    if not isinstance(value.get('engine',''),str) or len(value.get('engine',''))>100:raise ValueError('Version du moteur invalide.')
    if not isinstance(value.get('report_ids',[]),list) or any(type(i) is not int or i<=0 for i in value.get('report_ids',[])):raise ValueError('Rapports liés invalides.')
    validate_diagnostics(value.get('diagnostics',[]))
    if not isinstance(value.get('attempts',[]),list):raise ValueError('Historique d’analyse invalide.')
    for attempt in value.get('attempts',[]):
        if not isinstance(attempt,dict) or set(attempt)!={'at','engine','state','reasons','diagnostics','report_ids','action'} or attempt['state'] not in STATES or attempt['action'] not in {'analyze','ignore'}:raise ValueError('Historique d’analyse invalide.')
        datetime.fromisoformat(attempt['at'])
        if not isinstance(attempt['reasons'],list) or not isinstance(attempt['diagnostics'],list) or not isinstance(attempt['report_ids'],list):raise ValueError('Historique d’analyse invalide.')
        if any(not isinstance(r,str) for r in attempt['reasons']) or not isinstance(attempt['engine'],str) or any(type(i) is not int or i<=0 for i in attempt['report_ids']):raise ValueError('Historique d’analyse invalide.')
        validate_diagnostics(attempt['diagnostics'])


def validate_diagnostics(diagnostics):
    if not isinstance(diagnostics,list) or len(diagnostics)>64:raise ValueError('Diagnostics invalides.')
    for d in diagnostics:
        if not isinstance(d,dict) or not isinstance(d.get('name'),str) or d.get('status') not in {'ready','pending','unusable','complementary'}:raise ValueError('Diagnostic de fichier invalide.')
        for key in ('reasons','headers','corrections'):
            if key in d and (not isinstance(d[key],list) or any(not isinstance(s,str) for s in d[key])):raise ValueError('Diagnostic de fichier invalide.')
        if 'headers' in d and (len(d['headers'])>100 or any(len(h)>500 for h in d['headers'])):raise ValueError('En-tête sauvegardé invalide.')
        if 'columns' in d and (not isinstance(d['columns'],list) or len(d['columns'])!=len(d.get('headers',[])) or any(not isinstance(c,dict) or type(c.get('position')) is not int or not isinstance(c.get('header'),str) or c.get('role') not in {*amazon.FIELDS,None} for c in d['columns'])):raise ValueError('Colonnes sauvegardées invalides.')


def saved_archive(db,identity,ident):
    row=db.execute('SELECT summary FROM aff_snapshots WHERE id=? AND account_id=?',(ident,identity)).fetchone()
    value=json.loads(row['summary']).get('amazon_pending') if row else None
    if not value:raise ValueError('Archive introuvable pour ce compte.')
    return value


def save_analysis(db,identity,ident,value,state,reasons,diagnostics,report_ids,observed,action='analyze'):
    reasons=list(dict.fromkeys(r[:2000] for r in reasons))[:64] or ['Analyse terminée.']
    attempts=list(value.get('attempts',[]))
    # Retain the initial diagnostic of archives created before this engine.
    if not attempts and 'state' not in value:
        received=db.execute('SELECT observed_at FROM aff_snapshots WHERE id=? AND account_id=?',(ident,identity)).fetchone()['observed_at']
        attempts.append({'at':received,'engine':'legacy','state':'pending','reasons':value['reasons'], 'diagnostics':[],'report_ids':[],'action':'analyze'})
    attempts.append({'at':observed,'engine':ENGINE,'state':state,'reasons':reasons,'diagnostics':diagnostics,'report_ids':report_ids,'action':action})
    value={**value,'state':state,'reasons':reasons,'diagnostics':diagnostics,'report_ids':report_ids,'engine':ENGINE,'attempts':attempts}
    db.execute('UPDATE aff_snapshots SET summary=? WHERE id=? AND account_id=?',(json.dumps({'amazon_pending':value}),ident,identity))
    return value

def retain(db,identity,data,archive,reasons,observed):
    reasons=list(dict.fromkeys(r[:2000] for r in reasons))[:64]
    prior=next((r for r in archives(db,identity) if r['digest']==archive['digest']),None)
    if prior:ident=prior['id']
    else:
        value={'version':1,'archive':data['archive'],'digest':archive['digest'],'filename':str(data.get('filename') or 'amazon.zip')[:240],'reasons':reasons}
        ident=db.execute('INSERT INTO aff_snapshots(account_id,observed_at,summary,row_count,pages,source) VALUES(?,?,?,0,1,?)',
            (identity,observed,json.dumps({'amazon_pending':value}),'amazon-pending')).lastrowid
    return {'ok':True,'imported':False,'pending':True,'duplicate':bool(prior),'id':ident,'reasons':reasons,
            'message':'Archive conservée à vérifier. Les statistiques restent inchangées.'}

def select_references(values):
    groups={}
    for v in values:groups.setdefault((v['start'],v['end'],v['scope']),[]).append(v)
    warnings=[]
    for group in groups.values():
        if len({(v['kind'],v['view']) for v in group})!=len(group):raise ValueError('Plusieurs rapports concurrents de la même vue dans le ZIP.')
        for v in group:v['reference_metrics']=[]
        for metric in amazon.FIELDS[6:]:
            choices=[v for v in group if metric in amazon.available_metrics(v)]
            if not choices:continue
            choices.sort(key=lambda v:RANK[v['view']])
            selected=choices[0];amount=amazon.metric_totals(selected['rows'])[metric]
            dated=[v for v in choices if not v.get('date_basis') and amazon.metric_totals(v['rows'])[metric]==amount]
            if dated:selected=dated[0]
            selected['reference_metrics'].append(metric)
            if any(amazon.metric_totals(v['rows'])[metric]!=amount for v in choices):warnings.append('Des vues divergent : seule la référence vérifiée par la règle de priorité contribue aux totaux.')
        for v in group:v['contribution']='totals' if v['reference_metrics'] else 'detail'
    return warnings

def overlap(a,b):
    return a['start']<=b['end'] and b['start']<=a['end'] and (a['scope']==b['scope'] or 'all' in (a['scope'],b['scope']))

def reconcile(values,previous,received_at=None):
    """Preserve uncovered cells; never prorate an aggregate or infer missing zero days."""
    for i,v in enumerate(values):
        for other in values[:i]:
            if overlap(v,other) and amazon.reference_metrics(v)&amazon.reference_metrics(other):
                raise ValueError('Rapports de référence chevauchants dans le même ZIP.')
    carried=[];supersedes=[];changed_groups=set()
    for old in previous:
        remaining=copy.deepcopy(old);changed=False
        for v in values:
            if not overlap(old,v):continue
            common=amazon.reference_metrics(remaining)&amazon.reference_metrics(v)
            if not common:continue
            if received_at and old.get('observed_at','')>received_at:
                raise ValueError('Une référence plus récente existe déjà. Cette archive ancienne reste hors consolidation pour ne pas annuler une correction.')
            if old['scope']!=v['scope']:raise ValueError('Le périmètre de ce rapport chevauche un autre périmètre sans prouver son remplacement.')
            exact=(old['start'],old['end'])==(v['start'],v['end'])
            same_view=old.get('view','legacy')==v['view']
            if not same_view:
                if not exact:raise ValueError('Les vues de périodes différentes ne permettent pas un remplacement certain.')
                daily_equivalent=not v.get('date_basis') and all(amazon.metric_totals(old['rows'])[m]==amazon.metric_totals(v['rows'])[m] for m in common)
                if RANK.get(old.get('view','legacy'),4)<=RANK[v['view']] and not daily_equivalent:
                    v['reference_metrics']=[m for m in v['reference_metrics'] if m not in common]
                    v['contribution']='totals' if v['reference_metrics'] else 'detail'
                    continue
            daily=not old.get('date_basis') and not v.get('date_basis')
            if not exact and not daily:raise ValueError('Chevauchement de totaux non datés : impossible de répartir les montants avec certitude.')
            for metric in common:
                days={r['date'] for r in v['rows'] if r.get(metric) is not None}
                if daily and any(r.get(metric) is None and r['date'] in days for r in v['rows']):
                    raise ValueError('Correction quotidienne partielle : le dernier montant fiable est conservé.')
                for row in remaining['rows']:
                    if row.get(metric) is not None and (not daily or row['date'] in days):row[metric]=None;changed=True
            if changed:changed_groups.add((old['start'],old['end'],old['scope']))
        if changed:
            supersedes.append(old['id'])
            remaining['reference_metrics']=sorted(amazon.reference_metrics(remaining))
            if remaining['reference_metrics']:
                for key in ('id','observed_at','digest','supersedes'):remaining.pop(key,None)
                carried.append(remaining)
    supersedes.extend(old['id'] for old in previous if old.get('contribution')=='detail' and (old['start'],old['end'],old['scope']) in changed_groups)
    return carried,list(dict.fromkeys(supersedes))

def analyze(archive):
    values=[];diagnostics=[];warnings=[]
    labels={'start':'période','end':'période','scope':'périmètre des Tracking IDs','currency':'devise'}
    for file in archive['files']:
        diagnostic={'name':file['name'],'encoding':file.get('encoding','inconnu'),'status':'ready','reasons':[]}
        try:
            value,missing,notes=amazon.auto_report(file,{},diagnostic)
            diagnostic['reasons'].extend(notes)
            if missing:
                diagnostic['status']='pending'
                diagnostic['reasons'].append(', '.join(dict.fromkeys(labels[k] for k in missing['fields']))+' absent(e) du fichier.')
            elif amazon.misdated_annual_export(value):
                diagnostic['status']='pending'
                diagnostic['reasons'].append('Historique connu pour des dates incorrectes : période fiable non reconstruite, données exclues.')
            elif not amazon.available_metrics(value):
                diagnostic['status']='complementary'
                diagnostic['reasons'].append('Aucune valeur exploitable dans les indicateurs reconnus ; original conservé hors statistiques.')
            else:values.append(value);warnings.extend(notes)
        except amazon.ComplementaryReport as exc:
            diagnostic['status']='complementary';diagnostic['reasons'].append(str(exc))
        except (ValueError,csv.Error) as exc:
            diagnostic['status']='unusable';diagnostic['reasons'].append(str(exc))
        diagnostics.append(diagnostic)
    return values,diagnostics,warnings


def ingest(db,identity,data,observed,reanalyze=False):
    archive=amazon.inspect_archive(data)  # Unsafe containers are rejected, never stored.
    prior=next((v for v in archives(db,identity) if v['digest']==archive['digest']),None)
    received_at=prior['observed_at'] if prior else observed
    if prior and not reanalyze and (prior.get('engine')==ENGINE or prior['state']=='ignored'):
        return {'ok':True,'imported':False,'duplicate':True,'pending':prior['state'] in {'pending','unusable'},'state':prior['state'],'id':prior['id'],'reasons':prior['reasons']}
    history=[{'id':r['id'],**v} for r in db.execute('SELECT id,summary FROM aff_snapshots WHERE account_id=?',(identity,)) if (v:=json.loads(r['summary']).get('amazon'))]
    values,diagnostics,warnings=analyze(archive)
    reasons=[d['name']+' : '+r for d in diagnostics if d['status']!='ready' for r in d['reasons']]
    # Historical normalized contents, not just ZIP bytes, prevent old corrections
    # from returning to the totals, including repackaged or partially imported ZIPs.
    matched=[old['id'] for old in history if any(fingerprint(v)==fingerprint(old) for v in values)]
    new_values=[v for v in values if not any(fingerprint(v)==fingerprint(old) for old in history)]
    values=new_values
    carried=[];supersedes=[];blocked=False
    try:
        warnings.extend(select_references(values))
        carried,supersedes=reconcile(values,amazon.active_reports(db,identity),received_at)
    except ValueError as exc:
        reasons.append(str(exc));values=[];carried=[];supersedes=[];blocked=True
    db.execute('SAVEPOINT amazon_automatic')
    try:
        retained=retain(db,identity,data,archive,reasons or ['Archive originale conservée.'],observed)
        ident=retained['id'];saved=saved_archive(db,identity,ident);report_ids=list(dict.fromkeys([*saved.get('report_ids',[]),*matched]))
        if not retained['duplicate']:saved['state']='pending'
        for i,v in enumerate([*values,*carried]):
            if i<len(values):v['archive_digest']=archive['digest']
            if i==0:v['supersedes']=supersedes
            v['digest']=hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            amazon.validate_saved(v)
            report_id=db.execute('INSERT INTO aff_snapshots(account_id,observed_at,summary,row_count,pages,source) VALUES(?,?,?,?,1,?)',
                (identity,received_at,json.dumps({'amazon':v}),len(v['rows']),'amazon-zip')).lastrowid
            if i<len(values):report_ids.append(report_id)
        if values:db.execute('UPDATE aff_accounts SET last_success=?,last_error=NULL WHERE id=?',(observed,identity))
        statuses={d['status'] for d in diagnostics}
        state=('pending' if blocked or 'pending' in statuses else 'unusable' if 'unusable' in statuses else 'active' if report_ids else 'complementary')
        if state=='active' and not set(report_ids)&{r['id'] for r in amazon.active_reports(db,identity)}:state='replaced'
        if not reasons:reasons=['Rapports fiables intégrés ; aucune ancienne version réactivée.' if state=='active' else 'Version déjà connue, conservée sans réactivation des anciens montants.']
        save_analysis(db,identity,ident,saved,state,reasons,diagnostics,report_ids,observed)
        db.execute('RELEASE amazon_automatic')
    except Exception:
        db.execute('ROLLBACK TO amazon_automatic');db.execute('RELEASE amazon_automatic');raise
    counted=[{m:r.get(m) if m in amazon.reference_metrics(v) else None for m in amazon.FIELDS[6:]} for v in values for r in v['rows']]
    return {'ok':True,'id':ident,'state':state,'imported':bool(values),'duplicate':not values and bool(matched),'pending':state in {'pending','unusable'},'reasons':reasons,'replaced':len(supersedes),'warnings':list(dict.fromkeys(warnings)),
        'files':[{'name':v['filename'],'view':v['view'],'start':v['start'],'end':v['end'],'scope':v['scope'],'reference_metrics':v['reference_metrics']} for v in values],
        'totals':amazon.metric_totals(counted)}


def reprocess(db,identity,ident,observed):
    value=saved_archive(db,identity,ident)
    return ingest(db,identity,value,observed,reanalyze=True)


def reprocess_pending(db,identity,observed):
    # Materialize the IDs before processing; one failed analysis keeps its archive.
    results=[]
    for item in sorted(pending_reports(db,identity),key=lambda v:(v['observed_at'],v['id'])):
        try:results.append(reprocess(db,identity,item['id'],observed))
        except (ValueError,csv.Error) as exc:results.append({'id':item['id'],'ok':False,'message':str(exc)})
    return {'ok':True,'results':results,'message':f'{len(results)} archive(s) réanalysée(s).'}


def ignore(db,identity,ident,observed):
    value=saved_archive(db,identity,ident)
    if value.get('state','pending') not in {'pending','unusable','complementary','ignored'}:raise ValueError('Cette archive ne nécessite plus de classement sans suite.')
    if value.get('state')!='ignored':save_analysis(db,identity,ident,value,'ignored',['Classée sans suite par l’utilisateur. Les rapports déjà intégrés restent inchangés.'],value.get('diagnostics',[]),value.get('report_ids',[]),observed,'ignore')
    return {'ok':True,'message':'Archive classée sans suite, original et diagnostics conservés.'}


def report_history(db,identity):
    active={r['id'] for r in amazon.active_reports(db,identity)}
    saved=archives(db,identity);items=[]
    for row in db.execute('SELECT id,observed_at,source,summary FROM aff_snapshots WHERE account_id=? ORDER BY id DESC',(identity,)):
        v=json.loads(row['summary']).get('amazon')
        if not v or row['id'] in active:continue
        excluded=amazon.misdated_annual_export(v)
        original=next((a for a in saved if a['digest']==v.get('archive_digest')),None)
        items.append({'id':row['id'],'observed_at':row['observed_at'],'start':v['start'],'end':v['end'],'scope':v['scope'],'filename':v.get('filename',row['source']),
            'state':'excluded' if excluded else 'replaced','archive_id':original['id'] if original else None,
            'reason':('Cumul historique attribué à des journées incorrectes. ' + ('Original disponible : réanalyse possible, uniquement avec une période prouvée par le fichier.' if original else 'Original non conservé avec ce rapport ; aucune période fiable reconstructible à partir des seules lignes sauvegardées.')) if excluded else 'Rapport remplacé par une version plus récente ; conservé hors consolidation.'})
    return items
