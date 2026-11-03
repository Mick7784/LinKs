"""Automatic archive decisions; uncertain evidence is retained outside financial totals."""
import copy
import csv
import hashlib
import json
import amazon_affiliation as amazon

RANK={'category':0,'daily_trends':1,'tracking_id':2,'linked_product':3,'legacy':4}

def fingerprint(value):
    keys=('kind','start','end','scope','currency','rows')
    return json.dumps({**{k:value[k] for k in keys},'view':value.get('view','legacy'),'date_basis':value.get('date_basis')},sort_keys=True)

def pending_reports(db,identity):
    return [{'id':r['id'],'observed_at':r['observed_at'],**{k:v[k] for k in ('filename','digest','reasons')}}
        for r in db.execute('SELECT id,observed_at,summary FROM aff_snapshots WHERE account_id=? ORDER BY id DESC',(identity,))
        if (v:=json.loads(r['summary']).get('amazon_pending'))]

def validate_pending(value):
    if not isinstance(value,dict) or set(value)!={'version','archive','digest','filename','reasons'} or value['version']!=1:
        raise ValueError('Archive en attente invalide.')
    if not isinstance(value['filename'],str) or len(value['filename'])>240 or not isinstance(value['reasons'],list) or not 1<=len(value['reasons'])<=64 or any(not isinstance(r,str) or len(r)>2000 for r in value['reasons']):
        raise ValueError('Diagnostic en attente invalide.')
    if amazon.inspect_archive(value)['digest']!=value['digest']:raise ValueError('Empreinte de l’archive invalide.')

def retain(db,identity,data,archive,reasons,observed):
    reasons=list(dict.fromkeys(r[:2000] for r in reasons))[:64]
    prior=next((r for r in pending_reports(db,identity) if r['digest']==archive['digest']),None)
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

def reconcile(values,previous):
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

def ingest(db,identity,data,observed):
    archive=amazon.inspect_archive(data)  # Unsafe containers are rejected, never stored.
    history=[json.loads(r['summary']).get('amazon') for r in db.execute('SELECT summary FROM aff_snapshots WHERE account_id=?',(identity,))]
    history=[v for v in history if v]
    if any(v.get('archive_digest')==archive['digest'] for v in history):return {'ok':True,'imported':False,'duplicate':True}
    values=[];reasons=[];warnings=[]
    labels={'start':'période','end':'période','scope':'périmètre des Tracking IDs','currency':'devise'}
    for file in archive['files']:
        try:
            value,missing,notes=amazon.auto_report(file,{})
            if missing:
                reasons.append(file['name']+' : '+', '.join(dict.fromkeys(labels[k] for k in missing['fields']))+' absent(e) du fichier.')
                reasons.extend(notes)
            else:values.append(value);warnings.extend(notes)
        except (ValueError,csv.Error) as exc:reasons.append(file['name']+' : '+str(exc))
    if reasons:return retain(db,identity,data,archive,reasons,observed)
    if all(any(fingerprint(v)==fingerprint(old) for old in history) for v in values):return {'ok':True,'imported':False,'duplicate':True}
    try:
        warnings.extend(select_references(values))
        carried,supersedes=reconcile(values,amazon.active_reports(db,identity))
    except ValueError as exc:return retain(db,identity,data,archive,[str(exc)],observed)
    db.execute('SAVEPOINT amazon_automatic')
    try:
        for i,v in enumerate([*values,*carried]):
            if i<len(values):v['archive_digest']=archive['digest']
            if i==0:v['supersedes']=supersedes
            v['digest']=hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            amazon.validate_saved(v)
            db.execute('INSERT INTO aff_snapshots(account_id,observed_at,summary,row_count,pages,source) VALUES(?,?,?,?,1,?)',
                (identity,observed,json.dumps({'amazon':v}),len(v['rows']),'amazon-zip'))
        db.execute('UPDATE aff_accounts SET last_success=?,last_error=NULL WHERE id=?',(observed,identity))
        db.execute('RELEASE amazon_automatic')
    except Exception:
        db.execute('ROLLBACK TO amazon_automatic');db.execute('RELEASE amazon_automatic');raise
    counted=[{m:r.get(m) if m in amazon.reference_metrics(v) else None for m in amazon.FIELDS[6:]} for v in values for r in v['rows']]
    return {'ok':True,'imported':True,'duplicate':False,'pending':False,'replaced':len(supersedes),'warnings':list(dict.fromkeys(warnings)),
        'files':[{'name':v['filename'],'view':v['view'],'start':v['start'],'end':v['end'],'scope':v['scope'],'reference_metrics':v['reference_metrics']} for v in values],
        'totals':amazon.metric_totals(counted)}
