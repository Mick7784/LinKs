"""Review, transactional application and immutable versions for descriptions.

All offsets are Unicode code points. Preview is read-only. The caller holds
BEGIN IMMEDIATE for mutations; per-operation savepoints isolate partial failures.
"""
import copy
import hashlib
import re
import sqlite3
import uuid

import descriptions as d
import description_analysis as analysis
import description_search as search
import affiliate_partners as partners
import tracked_links


def digest(value):return hashlib.sha256(d.packed(value).encode('utf-8')).hexdigest()


def validate_options(value):
    if not isinstance(value,dict) or len(value)>1000:raise ValueError('Opérations invalides.')
    for key, option in value.items():
        d.ident(key)
        if not isinstance(option,dict) or set(option)-{'selected','action','link_id','source_id','section_id','merchant_id','target_url_id','allow_section','allow_subsection','allow_create','section_at','merchant_span'}:raise ValueError('Option d’opération invalide.')
        for field in ('selected','allow_section','allow_subsection','allow_create'):
            if field in option:d.flag(option,field)
        if option.get('action','') not in {'','remove','add','replace'}:raise ValueError('Action invalide.')
        for field in ('link_id','source_id','section_id','merchant_id','target_url_id'):
            if option.get(field):d.ident(option[field])
        if 'section_at' in option and (type(option['section_at']) is not int or option['section_at']<0):raise ValueError('Position invalide.')
        if 'merchant_span' in option:
            span=option['merchant_span']
            if not isinstance(span,dict) or set(span)!={'start','end','quote'} or any(type(span[k]) is not int for k in ('start','end')):raise ValueError('Emplacement marchand invalide.')
            d.text(span,'quote',d.MAX_TEXT)


def document(db,key,data):
    if not isinstance(data,dict):raise ValueError('Requête invalide.')
    doc=d.editor_document(d.get(db,d.TABLES[1],key))
    if data.get('expected_revision')!=doc['revision'] or type(data.get('expected_revision')) is not int:raise d.Conflict('Le brouillon a changé. Enregistrez et comparez à nouveau.')
    if data.get('text_hash') and data['text_hash']!=digest(doc['text']):raise d.Conflict('Le texte a changé. Comparez à nouveau.')
    d.validate_document(doc)
    return doc


def patch(doc,start,end,value,owner=None):
    before=doc['text'];delta=len(value)-(end-start)
    if not 0<=start<=end<=len(before):raise ValueError('Passage introuvable.')
    doc['text']=before[:start]+value+before[end:]
    for a in doc['sections']:
        if a['status']!='confirmed':a['candidates']=[];continue
        if a['id']==owner and a['start']<=start<=end<=a['end']:a['end']+=delta
        elif a['end']<=start:pass
        elif a['start']>=end:a['start']+=delta;a['end']+=delta
        elif a['start']<=start<=end<=a['end']:a['end']+=delta
        else:a.update(status='ambiguous',start=None,end=None,candidates=[]);continue
        a['quote']=doc['text'][a['start']:a['end']]


def anchor(doc,section_id,option):
    definition=next((s for s in doc['template_snapshot']['sections'] if s['id']==section_id),None)
    a=next((s for s in doc['sections'] if s['id']==section_id),None)
    if not definition or not a:raise ValueError('Section cible absente du modèle copié.')
    if a['status']=='confirmed':return a,definition
    if not option.get('allow_section'):raise ValueError('Section absente ou ambiguë : confirmez son emplacement ou autorisez sa création à la sélection.')
    point=option.get('section_at')
    if type(point) is not int or point>len(doc['text']) or any(x['status']=='confirmed' and x['start']<point<x['end'] for x in doc['sections']):raise ValueError('Placez le curseur hors d’une autre section, à l’emplacement souhaité.')
    if a['quote'] and a['quote'] in doc['text']:raise ValueError('La section existe encore : associez son passage plutôt que de la recréer.')
    value=definition['heading'];prefix='\n\n' if point and not doc['text'][:point].endswith('\n\n') else '';suffix='\n\n' if point<len(doc['text']) else ''
    patch(doc,point,point,prefix+value+suffix)
    a.update(status='confirmed',start=point+len(prefix),end=point+len(prefix)+len(value),quote=value,candidates=[])
    return a,definition


def line_positions(text,start,end):
    offset=start
    for line in text[start:end].splitlines(keepends=True):
        yield offset,offset+len(line.rstrip('\r\n')),line.rstrip('\r\n')
        offset+=len(line)


def location(doc,op):
    a,definition=anchor(doc,op['section_id'],op['option'])
    sub=next((m for m in definition['merchants'] if m['id']==op.get('merchant_id')),None)
    start,end=a['start'],a['end']
    if op.get('merchant_id') and not sub:raise ValueError('Sous-section marchande supprimée de la copie du modèle.')
    if sub:
        span=op['option'].get('merchant_span')
        if span:
            if not start<=span['start']<=span['end']<=end or doc['text'][span['start']:span['end']]!=span['quote']:raise ValueError('La sous-section associée a changé : confirmez à nouveau sa sélection.')
            start,end=span['start'],span['end']
        else:
            headings=[(p,q,line,m['id']) for p,q,line in line_positions(doc['text'],start,end) for m in definition['merchants'] if m['heading'] and line.strip()==m['heading'].strip()]
            found=[h for h in headings if h[3]==sub['id']]
            if len(found)>1:raise ValueError('Titre marchand répété : associez explicitement le passage.')
            if not found:
                if not op['option'].get('allow_subsection'):raise ValueError('Sous-section absente ou renommée : associez-la ou autorisez explicitement son ajout.')
                order=[m['id'] for m in definition['merchants']];later=[h[0] for h in headings if order.index(h[3])>order.index(sub['id'])]
                point=min(later) if later else end
                value=('\n\n' if point and not doc['text'][:point].endswith('\n\n') else '')+sub['heading']+'\n'
                patch(doc,point,point,value,a['id']);start=point+len(value);end=start
            else:
                start=found[0][1];end=min([h[0] for h in headings if h[0]>found[0][0]] or [end])
    owner=sub or definition;point=end
    # Keep permanent links and trailing copy after newly inserted products.
    for binding in owner['links']:
        for url in [binding.get('reference_url'),op.get('binding_urls',{}).get(binding['id'])]:
            if url:
                for p,q,line in line_positions(doc['text'],start,end):
                    if url in line:point=min(point,p)
    if owner.get('after_text'):
        count=doc['text'][start:end].count(owner['after_text'])
        if count>1:raise ValueError('Texte de fin répété : emplacement ambigu.')
        if count==1:point=min(point,doc['text'].find(owner['after_text'],start,end))
    return a,sub,start,end,point


def replace_urls(doc,raw,value):
    occurrences=[u for u in analysis.urls(doc['text']) if u['url']==raw]
    if not occurrences:raise ValueError('L’URL à modifier n’est plus présente.')
    for u in reversed(occurrences):patch(doc,u['start'],u['end'],value)


def edit(doc,op,url,mapping):
    if op['kind']=='cleanup':return hide_empty(doc)
    raw=mapping.get(op.get('raw'),op.get('raw'))
    if op['kind'] in {'replace','remove'}:
        if raw==url and op['kind']=='replace':return False
        replace_urls(doc,raw,'' if op['kind']=='remove' else url);mapping[op['raw']]='' if op['kind']=='remove' else url
        return True
    line=None
    if op['kind']=='move':
        found=[u for u in analysis.urls(doc['text']) if u['url']==raw]
        if len(found)!=1:raise ValueError('Déplacement ambigu : l’URL doit apparaître une seule fois.')
        u=found[0];start=doc['text'].rfind('\n',0,u['start'])+1;end=doc['text'].find('\n',u['end']);end=len(doc['text']) if end<0 else end
        line=doc['text'][start:end];prefix=doc['text'][start:u['start']].strip();suffix=doc['text'][u['end']:end].strip()
        if suffix or (prefix and not prefix.endswith(':')):raise ValueError('Lien intégré à une phrase : déplacez manuellement le passage dans l’éditeur.')
        # Validate destination before removing the exact source line.
        target=copy.deepcopy(doc);_,_,lo,hi,_=location(target,op)
        if lo<=start<hi:return False
        patch(doc,start,min(len(doc['text']),end+1),'')
    a,sub,start,end,point=location(doc,op)
    destination=op.get('destination')
    known=set(op.get('equivalent_urls',[]))|{url}
    if any(u['url'] in known for u in analysis.urls(doc['text'][start:end])):return False
    if op['kind']=='add' and any(u['url'] in op.get('product_urls',[]) for u in analysis.urls(doc['text'][start:end])):raise ValueError('Ce produit possède déjà un lien chez ce marchand. Choisissez explicitement l’URL à remplacer.')
    # Applied product identities prevent a second merchant insertion even if a
    # catalogue title changed. Existing lines are never silently reordered.
    for used in doc.get('workflow',{}).get('links',[]):
        if used.get('product_id') and used['product_id']==op.get('product_id') and used.get('merchant_id')==op.get('merchant_id') and used.get('url') in doc['text'][start:end]:raise ValueError('Ce produit est déjà présent chez ce marchand ; choisissez un remplacement explicite.')
    value=line if line is not None else op['label']+(' : ' if op['label'] and op['origin']!='permanent' else '')+url
    prefix='' if point==0 or doc['text'][point-1]=='\n' else '\n'
    suffix='' if point<len(doc['text']) and doc['text'][point]=='\n' else '\n'
    patch(doc,point,point,prefix+value+suffix,a['id'])
    return True


def source(db,ident,doc):
    row=db.execute('SELECT id,name,active FROM tracking_sources WHERE id=?',(ident,)).fetchone()
    ids=set(tracked_links.platform_source_ids(db,'youtube'))
    ids.update(b['source_id'] for s in doc['template_snapshot']['sections'] for owner in [s,*s['merchants']] for b in owner['links'] if b['source_id'])
    if not row or not row['active'] or (ident not in ids and row['name'] not in {'YouTube','YouTube Description','YouTube Post'}):raise ValueError('Choisissez une source YouTube existante et active.')
    return dict(row)


def hide_empty(doc):
    changed=False
    for definition in reversed(doc['template_snapshot']['sections']):
        a=next(x for x in doc['sections'] if x['id']==definition['id'])
        if a['status']!='confirmed':continue
        for sub in reversed(definition['merchants']):
            if not sub['hide_if_empty'] or not sub['heading']:continue
            lines=list(line_positions(doc['text'],a['start'],a['end']))
            hits=[x for x in lines if x[2].strip()==sub['heading'].strip()]
            if len(hits)!=1:continue
            start,end,_=hits[0];next_heading=min([p for p,q,line in lines if p>start and any(m['heading'] and line.strip()==m['heading'].strip() for m in definition['merchants'])] or [a['end']])
            if not doc['text'][end:next_heading].strip():patch(doc,start,next_heading,'',a['id']);changed=True
        if definition['hide_if_empty'] and doc['text'][a['start']:a['end']].strip()==definition['heading'].strip():
            start,end=a['start'],a['end'];quote=a['quote'];patch(doc,start,end,'',a['id']);a.update(status='ambiguous',start=None,end=None,quote=quote,candidates=[]);changed=True
    return changed


def resolve(db,doc,op,items,origin):
    if op['kind'] in {'move','remove','cleanup'}:op.update(url=op.get('raw',''),destination='',pending_create=False);return
    ident=op.get('link_id','');item=items.get(ident)
    if ident and (not item or not item['enabled'] or item['archived']):raise ValueError('Fiche absente, archivée ou suspendue.')
    if op.get('prepared'):
        old=op['prepared'];merchant=op['merchant']
        data={'document':{k:doc[k] for k in ('text','sections','analysis_version','products','selections','manual_order') if k in doc},'product_id':op['product_id'],'merchant':merchant,'url':old['original_url'],'label':op['label'],'link_id':ident if item and item['url']==old['original_url'] else ''}
        fresh=search.prepare_link(db,doc['id'],data,origin)
        if any(fresh[k]!=old[k] for k in ('url','partner_id','mode')):raise ValueError('Préparation obsolète : destination ou règle du partenaire modifiée. Préparez à nouveau.')
        if op['kind']=='add' and not any(p['section_id']==op.get('section_id') and p['merchant_id']==op.get('merchant_id') for p in fresh['placements']):raise ValueError('Choisissez la sous-section du marchand dans la copie du modèle.')
        if old['original_url']!=op.get('input_url'):raise ValueError('L’URL collée doit être préparée à nouveau.')
        if fresh['duplicates'] and not ident:
            if len(fresh['duplicates'])!=1:raise ValueError('Plusieurs doublons : choisissez la fiche à réutiliser.')
            ident=fresh['duplicates'][0]['id'];item=items.get(ident)
        if ident and not any(x['id']==ident for x in fresh['duplicates']):raise ValueError('La fiche ne correspond plus à la destination préparée.')
        if item and (not item['enabled'] or item['archived']):raise ValueError('La fiche correspondante n’est plus disponible.')
        op.update(destination=fresh['url'],partner_id=fresh['partner_id'],original_url=fresh['original_url'],link_id=ident)
    elif item:op.update(destination=item['url'],partner_id=item['partner_id'],original_url=item['original_url'])
    elif op.get('amazon') and op.get('raw'):op.update(destination=op['raw'],partner_id='',original_url=op['raw'])
    elif op['option'].get('allow_create') and op.get('raw') and not op.get('amazon'):
        from urllib.parse import urlsplit
        raw=op['raw']
        if not partners.http_url(raw) or (urlsplit(raw).hostname or '').lower().rstrip('.')==(urlsplit(origin).hostname or '').lower().rstrip('.'):raise ValueError('Une destination externe HTTP(S) exacte est requise.')
        preview=partners.preview_tracked(db,{'url':raw,'detect':True})
        if preview['duplicates']:raise ValueError('Cette destination existe déjà : choisissez sa fiche avant de créer.')
        op.update(destination=preview['url'],partner_id=preview['partner_id'],original_url=raw)
    else:raise ValueError('Aucune fiche choisie. Préparez le lien marchand ou sélectionnez une correspondance.')
    if analysis.kind(op['destination'])=='amazon' or op.get('amazon'):
        if op.get('raw_kind')=='links':raise ValueError('Lien LinKs vers Amazon : fournissez une URL directe dans le parcours Amazon.')
        if not search.valid_url(op['destination'],'amazon'):raise ValueError('Destination Amazon directe invalide.')
        if not op.get('prepared') and op.get('raw') and analysis.kind(op['raw'])=='amazon':op['destination']=op['raw']
        op.update(amazon=True,url=op['destination'],source_id='',pending_create=False)
        return
    src=source(db,op.get('source_id',''),doc);op['source_name']=src['name']
    publications=(item or {}).get('publications',[])
    publication=next((p for p in publications if p['source_id']==src['id'] and p['active']),None)
    op.update(url=publication['url'] if publication else op['destination'],pending_create=not bool(publication))
    op['equivalent_urls']=[p['url'] for p in publications]+[op['destination'],op['original_url']]


def operations(db,doc,origin):
    result=analysis.analyze(db,doc,origin);items,_,_=analysis.catalogue(db,origin,doc['template_snapshot'])
    options=doc['selections'].get('operations',{});validate_options(options)
    choices=doc['selections'].get('description_analysis',{});ops=[]
    for p in result['proposals']:
        value={**p,**choices.get(p['id'],{})};url=next((u for u in result['urls'] if u['id']==p.get('url_id')),None)
        section=value.get('target_section','affiliate');merchant=''
        if p['kind']=='add':
            item=items.get(value.get('link_id'),{});kind=analysis.kind(item.get('url',''))
            merchant=kind if kind in search.MERCHANTS else '';section='videos' if kind=='youtube' else 'affiliate'
        if p['kind']=='move' and url:
            item=items.get((url.get('known') or {}).get('link_id'),{});kind=analysis.kind(item.get('url') or url['url']);merchant=kind if kind in search.MERCHANTS and section=='affiliate' else ''
        ops.append({**value,'kind':{'reuse':'replace','add':'add','move':'move'}[p['kind']], 'raw':url['url'] if url else '', 'raw_kind':url['kind'] if url else '', 'section_id':section,'merchant_id':merchant,'origin':'analysis'})
        if url and (url.get('known') or {}).get('revoked'):ops[-1]['invalid']='Alias LinKs révoqué : choisissez une destination valide.'
    for pid,state in doc['selections'].get('merchant_search',{}).get('products',{}).items():
        for merchant,v in state['merchants'].items():
            if not v.get('prepared'):continue
            raw=v['prepared']['original_url'];present=any(u['url']==raw for u in result['urls'])
            ops.append({**v,'id':'merchant-'+pid+'-'+merchant,'kind':'replace' if present else 'add','raw':raw if present else '', 'product_id':pid,'merchant':merchant,'amazon':merchant=='amazon','origin':'merchant','input_url':v.get('url_input','')})
    binding_urls={}
    for s in doc['template_snapshot']['sections']:
        for owner in [s,*s['merchants']]:
            for b in owner['links']:
                url,_=d.resolved_link(db,b,origin);binding_urls[b['id']]=url
                if url and url in doc['text']:continue
                if b['reference_url'] and b['reference_url'] in doc['text']:continue
                ops.append({'id':'permanent-'+b['id'],'kind':'add','label':b['label'],'selected':False,'link_id':b['link_id'],'source_id':b['source_id'],'section_id':s['id'],'merchant_id':owner['id'] if owner is not s else '', 'origin':'permanent'})
    ops.append({'id':'hide-empty','kind':'cleanup','selected':True,'label':'Masquer les sections facultatives vides','origin':'cleanup'})
    current_ids={op['id'] for op in ops}
    for ident in set(choices)|set(options):
        if ident not in current_ids and options.get(ident,{}).get('selected',choices.get(ident,{}).get('selected',False)):
            ops.append({'id':ident,'kind':'replace','selected':True,'label':choices.get(ident,{}).get('label','Proposition antérieure'),'origin':'analysis','invalid':'Cette proposition n’existe plus dans le texte courant.'})
    rank=doc.get('manual_order',[]);positions={p['id']:p['position'] for p in result['products']}
    for op in ops:
        option=options.get(op['id'],{});op['option']=option;op.update({k:v for k,v in option.items() if k in {'selected','link_id','source_id','section_id','merchant_id'}})
        if option.get('action')=='remove' and op.get('raw'):op['kind']='remove'
        if option.get('target_url_id'):
            target=next((u for u in result['urls'] if u['id']==option['target_url_id']),None)
            if target:op.update(kind='replace',raw=target['url'],raw_kind=target['kind'])
            else:op['invalid']='L’URL de remplacement choisie n’est plus présente.'
        if option.get('action')=='add':op['kind']='add'
        op.setdefault('selected',False);op.setdefault('label','');op.setdefault('product_id','');op['binding_urls']=binding_urls
        op['product_urls']=[u['url'] for u in result['urls'] if u['product_id']==op['product_id'] and (u['kind']==op.get('merchant_id') or any(analysis.kind(items[m['link_id']]['url'])==op.get('merchant_id') for m in u['matches']))]
    # A prepared merchant replacement supersedes the earlier proposal for that URL.
    replacements={o.get('raw') for o in ops if o['origin']=='merchant' and o['selected'] and o['kind']=='replace'}
    for op in ops:
        if op['origin']=='analysis' and op['kind']=='replace' and op.get('raw') in replacements:op['selected']=False;op['note']='Remplacement pris en charge par la préparation marchande.'
    ops.sort(key=lambda o:(3 if o['kind']=='cleanup' else 0 if o['kind'] in {'replace','remove'} else 2 if o['kind']=='move' else 1,rank.index(o['product_id']) if o['product_id'] in rank else len(rank),positions.get(o['product_id'],10**9),o['id']))
    return ops,result,items


def compare(db,key,data,origin):
    doc=document(db,key,data);ops,result,items=operations(db,doc,origin);proposed=copy.deepcopy(doc);mapping={}
    for op in ops:
        op['status']='ignored';op['reason']=op.get('note','Non sélectionnée.');before=copy.deepcopy(proposed);before_map=copy.deepcopy(mapping)
        if not op['selected']:continue
        try:
            if op.get('invalid'):raise ValueError(op['invalid'])
            if op.get('product_id') and not any(p['id']==op['product_id'] for p in result['products']):raise ValueError('Le produit n’est plus explicitement présent.')
            if op['kind'] not in {'remove','move','cleanup'} and op.get('matches') is not None and op.get('link_id') and not any(m['link_id']==op['link_id'] for m in op['matches']):raise ValueError('La correspondance choisie n’est plus valide.')
            resolve(db,doc,op,items,origin)
            changed=edit(proposed,op,op.get('url',''),mapping)
            # A not-yet-created publication is previewed with its real destination.
            # That destination may equal the existing raw URL; the confirmed
            # operation still replaces it with the publication allocated on apply.
            if op['kind']=='replace' and op.get('pending_create'):changed=True
            op.update(status='ready' if changed else 'ignored',reason=('Lien suivi à créer ; l’aperçu affiche sa destination réelle.' if op.get('pending_create') else 'Opération prête.') if changed else 'Déjà présent, sans changement.')
        except (ValueError,KeyError) as exc:
            proposed=before;mapping=before_map;op.update(status='obsolete',reason=str(exc))
    public_ops=[{k:v for k,v in o.items() if k not in {'prepared','matches','binding_urls'}} for o in ops]
    plan={'expected_revision':doc['revision'],'text_hash':digest(doc['text']),'before':doc['text'],'after':proposed['text'],'operations':public_ops}
    plan['plan_hash']=digest(plan)
    plan['warnings']=['Amazon : insertion directe sans statistiques LinKs. La structure d’une URL ne garantit ni son affiliation ni son fonctionnement.'] if any(u['amazon'] for u in result['urls']) or any(o.get('amazon') and o['selected'] for o in ops) else []
    for op in ops:
        if op.get('amazon') and op.get('url') and not re.match(r'https?://',op['url'],re.I):plan['warnings'].append('URL Amazon sans schéma HTTP(S) : elle risque de ne pas être cliquable sur YouTube. Elle reste inchangée.')
    plan.update(urls=[{'id':u['id'],'url':u['url']} for u in result['urls']],catalogue=[{'id':i['id'],'name':i['name']} for i in items.values() if i['enabled'] and not i['archived']],sources=[dict(r) for r in db.execute('SELECT id,name FROM tracking_sources WHERE active=1')])
    return plan


def apply(db,key,data,origin,url_valid=partners.http_url):
    mutation=d.ident(data.get('mutation_id'));fingerprint=digest({k:v for k,v in data.items() if k!='mutation_id'})
    existing=d.editor_document(d.get(db,d.TABLES[1],key));receipt=existing.get('workflow',{}).get('receipts',{}).get(mutation)
    if receipt:
        if receipt['digest']!=fingerprint:raise d.Conflict('Validation déjà utilisée avec un autre contenu.')
        return {'document':existing,'results':receipt['results'],'replayed':True}
    plan=compare(db,key,data,origin)
    if data.get('plan_hash')!=plan['plan_hash']:raise d.Conflict('La préparation ou le catalogue a changé. Comparez à nouveau avant de valider.')
    doc=existing;ops,_,items=operations(db,doc,origin);states={o['id']:o for o in plan['operations']};mapping={};results=[]
    workflow=doc.setdefault('workflow',{'receipts':{},'links':[],'results':{}})
    for op in ops:
        state=states[op['id']]
        if state['status']!='ready':
            if op['selected']:results.append({'id':op['id'],'status':state['status'],'reason':state['reason']})
            continue
        before=copy.deepcopy(doc);before_map=copy.deepcopy(mapping);db.execute('SAVEPOINT description_operation')
        try:
            resolve(db,doc,op,items,origin);url=op.get('url','')
            if op['kind'] not in {'move','remove','cleanup'} and not op.get('amazon'):
                ident=op.get('link_id')
                if not ident:
                    preview=partners.preview_tracked(db,{'url':op['original_url'],'partner_id':op['partner_id']})
                    if preview['url']!=op['destination']:raise ValueError('La règle d’affiliation a changé.')
                    if preview['duplicates']:
                        if len(preview['duplicates'])!=1:raise ValueError('Doublons ambigus : choisissez une fiche.')
                        ident=preview['duplicates'][0]['id']
                    else:
                        saved=partners.save_tracked(db,{'name':op['label'] or 'Lien de description','url':op['original_url'],'partner_id':op['partner_id'],'expected_url':preview['url']},url_valid,d.stamp());ident=saved['id']
                    op['link_id']=ident
                # Existing publications are reused byte for byte, including a
                # historical /go/token without allocating a replacement alias.
                if op.get('pending_create'):url=tracked_links.token_link(db,ident,op['source_id'],origin,d.stamp())['url']
            changed=edit(doc,op,url,mapping)
            if not changed:db.execute('ROLLBACK TO description_operation')
            else:
                if op['kind'] not in {'remove','cleanup'}:doc.setdefault('workflow',{}).setdefault('links',[]).append({k:op.get(k,'') for k in ('id','link_id','source_id','destination','product_id','section_id','merchant_id')}|{'url':url})
                doc.setdefault('analysis_version',1);doc['selections'].setdefault('operations',{}).setdefault(op['id'],{})['selected']=False
                if op['origin']=='analysis':doc['selections'].setdefault('description_analysis',{}).setdefault(op['id'],{})['selected']=False
                if op['origin']=='merchant':doc['selections']['merchant_search']['products'][op['product_id']]['merchants'][op['merchant']]['selected']=False
            result={'id':op['id'],'status':'applied','reason':'Appliquée.' if changed else 'Déjà présente.','url':url}
            db.execute('RELEASE description_operation');results.append(result)
        except (ValueError,sqlite3.Error,OSError) as exc:
            db.execute('ROLLBACK TO description_operation');db.execute('RELEASE description_operation');doc=before;mapping=before_map
            results.append({'id':op['id'],'status':'failed','reason':str(exc)})
    workflow=doc.setdefault('workflow',{});workflow.setdefault('results',{}).update({r['id']:r for r in results})
    receipts=workflow.setdefault('receipts',{});receipts[mutation]={'digest':fingerprint,'results':results}
    # Older requests remain rejected by their revision even after receipt pruning.
    while len(receipts)>20:del receipts[next(iter(receipts))]
    saved=d.update(db,d.TABLES[1],key,d.validate_document(doc),existing['revision'])
    return {'document':d.editor_document(saved),'results':results,'replayed':False}


def finalize(db,key,data,origin):
    mutation=d.ident(data.get('mutation_id'));version_id=uuid.uuid5(uuid.NAMESPACE_URL,'links:description-version:'+key+':'+mutation).hex
    previous=db.execute('SELECT * FROM description_versions WHERE id=?',(version_id,)).fetchone()
    fingerprint=digest(data)
    if previous:
        version=d.decode(previous)
        if version.get('finalization_digest')!=fingerprint:raise d.Conflict('Finalisation déjà utilisée avec un autre contenu.')
        return {'version':version,'document':d.editor_document(d.get(db,d.TABLES[1],key)),'replayed':True}
    doc=document(db,key,data)
    if len(doc['text'])>5000:raise ValueError('La description dépasse la limite de 5 000 caractères YouTube.')
    if not doc['text'].strip():raise ValueError('La description est vide.')
    plan=compare(db,key,data,origin)
    if data.get('plan_hash')!=plan['plan_hash']:raise d.Conflict('Le texte ou les propositions ont changé. Vérifiez à nouveau avant de finaliser.')
    if any(o['selected'] and o['status'] in {'ready','obsolete'} for o in plan['operations']):
        if data.get('ignore_remaining') is not True:raise ValueError('Appliquez les opérations restantes ou confirmez explicitement leur abandon pour cette version.')
    items,tokens,aliases=analysis.catalogue(db,origin,doc['template_snapshot']);snapshots=[]
    from urllib.parse import urlsplit
    for occurrence in analysis.urls(doc['text']):
        url=occurrence['url'];parsed=urlsplit(analysis.absolute(url));known=None
        if parsed.netloc==urlsplit(origin).netloc:known=tokens.get(parsed.path[4:]) if parsed.path.startswith('/go/') else aliases.get(parsed.path[1:])
        item=items.get((known or {}).get('link_id'))
        association=next((x for x in reversed(doc.get('workflow',{}).get('links',[])) if x['url']==url),{})
        if not item and association.get('link_id'):item=items.get(association['link_id'])
        amazon=analysis.kind(url)=='amazon'
        snapshots.append({'url':url,'link_id':(item or {}).get('id',''),'source_id':'' if amazon else (known or association).get('source_id',''),
                          'destination':url if amazon else (item or {}).get('url',url),'available':not bool((known or {}).get('revoked')) and bool(item['enabled'] and not item['archived']) if item else None, 'observed_at':d.stamp()})
    version=d.validate_document({**doc,'status':'finalized','description_id':key,'finalized_at':d.stamp(),'links':snapshots,'finalization_digest':fingerprint,'ignored_remaining':data.get('ignore_remaining') is True},True)
    version.pop('workflow',None)
    saved=d.insert(db,d.TABLES[2],version,version_id)
    doc['last_finalized_version']=saved['id'];doc['last_finalized_at']=saved['finalized_at']
    updated=d.update(db,d.TABLES[1],key,d.validate_document(doc),doc['revision'])
    return {'version':saved,'document':d.editor_document(updated),'replayed':False}


def restore(db,version_id,data):
    version=d.get(db,d.TABLES[2],version_id);mutation=d.ident(data.get('mutation_id'));key=uuid.uuid5(uuid.NAMESPACE_URL,'links:restore-version:'+version_id+':'+mutation).hex
    previous=db.execute('SELECT * FROM description_drafts WHERE id=?',(key,)).fetchone()
    if previous:return d.editor_document(d.decode(previous))
    payload=d.validate_document({**version,'status':'draft','title':version['title'][:140]+' — restauré'})
    for field in ('description_id','finalized_at','links','finalization_digest','ignored_remaining','last_finalized_version','last_finalized_at','last_mutation'):payload.pop(field,None)
    payload['restored_from']=version_id
    # A restored text is already applied. Its old pending suggestions are ignored.
    for v in payload['selections'].get('description_analysis',{}).values():v['selected']=False
    for v in payload['selections'].get('operations',{}).values():v['selected']=False
    for product in payload['selections'].get('merchant_search',{}).get('products',{}).values():
        for v in product['merchants'].values():v['selected']=False
    return d.editor_document(d.insert(db,d.TABLES[1],payload,key))
