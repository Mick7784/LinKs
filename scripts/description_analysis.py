"""Read-only description analysis. No fetch, redirect, token allocation or affiliate rule.

Results are disposable views over the existing catalogue, never a product database.
Only explicit references and draft-local choices survive in description payloads.
"""
import hashlib
import re
import unicodedata
from urllib.parse import urlsplit

import affiliate_partners
import tracked_links
import url_inspection

URL = re.compile(r'(?:https?://|www\.|(?<![\w@])(?:amzn\.to|link\.amazon)/)[^\s<>"«»“”]+', re.I)
GENERIC = {'zigbee','mqtt','home assistant','wifi','wi fi','cpl','node red','zigbee2mqtt','matter','thread','bluetooth','usb','poe','domotique','amazon','domadoo','smlight','sonoff'}
STOP = {'de','du','des','le','la','les','un','une','avec','et','pour','sur','en','a','d','v','w'}
ACCESSORIES = {'alimentation','cable','support','adaptateur','injecteur','antenne','chargeur','batterie'}


def normal(value):
    return ' '.join(re.findall(r'[a-z0-9]+', ''.join(c for c in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(c))))


def identity(kind, value):
    return kind+'-'+hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]


def absolute(raw):
    return raw if re.match(r'https?://', raw, re.I) else 'https://'+raw


def kind(raw):
    try:host=(urlsplit(absolute(raw)).hostname or '').lower().rstrip('.')
    except ValueError:return 'other'
    if host in {'amzn.to','link.amazon'} or re.fullmatch(r'(?:[\w-]+\.)*amazon\.[a-z.]+',host):return 'amazon'
    if host=='domadoo.fr' or host.endswith('.domadoo.fr'):return 'domadoo'
    if host=='youtu.be' or host=='youtube.com' or host.endswith('.youtube.com'):return 'youtube'
    return 'other'


def urls(content):
    result=[]
    for match in URL.finditer(content):
        raw=match.group()
        # Surrounding prose delimiters are not part of the URL. Query/fragment
        # punctuation can be affiliate data: leave it untouched, even if unusual.
        if '?' not in raw and '#' not in raw:raw=raw.rstrip('.,;!?:')
        wrapped=match.start()>0 and content[match.start()-1] in '([{'
        while raw and raw[-1] in ')]}' and ('?' not in raw and '#' not in raw or wrapped) and raw.count(raw[-1])>raw.count({')':'(',']':'[','}':'{'}[raw[-1]]):raw=raw[:-1]
        if not raw:continue
        try:
            target=urlsplit(absolute(raw))
            if not target.hostname or target.username or target.password:continue
            target.port
        except ValueError:continue
        result.append({'url':raw,'start':match.start(),'end':match.start()+len(raw),'kind':kind(raw)})
    return result


def catalogue(db, origin, template):
    """Adapter over existing records; all source/token identities remain separate."""
    items={r['id']:dict(r) for r in db.execute('SELECT id,name,url,archived,enabled FROM tracked_links ORDER BY id')}
    youtube=set(tracked_links.platform_source_ids(db,'youtube'))
    youtube.update(r['id'] for r in db.execute("SELECT id FROM tracking_sources WHERE name IN ('YouTube Description','YouTube Post','YouTube')"))
    for section in template['sections']:
        for owner in [section,*section['merchants']]:
            youtube.update(b['source_id'] for b in owner['links'] if b['source_id'])
    tokens={};aliases={}
    for item in items.values():
        item.update(affiliate_partners.link_metadata(db,item['id'],item['url']))
        item['publications']=[]
        try:partner=item['partner_id'] or affiliate_partners.detect(db,item['url'])
        except ValueError:partner=''
        item['merchant']=partner or kind(item['url'])
        if item['merchant']=='other':item['merchant']=(urlsplit(item['url']).hostname or 'Autre')
    for row in db.execute('''SELECT t.token,t.link_id,t.source_id,s.name,s.active
                            FROM tracked_tokens t JOIN tracking_sources s ON s.id=t.source_id'''):
        if row['link_id'] not in items:continue
        publication={'id':row['token'],'source_id':row['source_id'],'source_name':row['name'],
                     'active':bool(row['active']),'youtube':row['source_id'] in youtube,
                     'url':origin.rstrip('/')+'/go/'+row['token']}
        items[row['link_id']]['publications'].append(publication)
        tokens[row['token']]={'link_id':row['link_id'],'source_id':row['source_id'],'revoked':False}
    for row in db.execute('SELECT * FROM short_aliases ORDER BY created_at,code'):
        target=tokens.get(row['target_token'])
        if target:
            aliases[row['code']]={**target,'revoked':bool(row['revoked'])}
            publication=next(p for p in items[target['link_id']]['publications'] if p['id']==row['target_token'])
            if not row['revoked'] and '/go/' in publication['url']:publication['url']=origin.rstrip('/')+'/'+row['code']
        else:
            campaign=db.execute('SELECT promotion_id,deleted FROM story_links WHERE token=?',(row['target_token'],)).fetchone()
            if campaign:aliases[row['code']]={'campaign_id':campaign[0],'source_id':row['source'],'revoked':bool(row['revoked'] or campaign[1])}
    for row in db.execute('SELECT token,promotion_id,deleted FROM story_links'):
        tokens[row['token']]={'campaign_id':row['promotion_id'],'source_id':'','revoked':bool(row['deleted'])}
    return items,tokens,aliases


def scopes(content, anchors, template):
    """Use confirmed ranges first; ambiguous headings delimit exclusion only.

    Nothing here confirms or changes an editor anchor. Unresolved permanent
    ranges suppress product detection rather than treating boilerplate as video.
    """
    lines=[];offset=0
    for raw in content.splitlines(keepends=True):
        line=raw.rstrip('\r\n');lines.append({'text':line,'start':offset,'end':offset+len(line)});offset+=len(raw)
    headings=[];definitions={s['id']:s for s in template['sections']}
    for definition in template['sections']:
        anchor=next((a for a in anchors if a['id']==definition['id']),{})
        names={definition['heading'].strip()}
        if definition['heading'] and anchor.get('quote'):names.add(anchor['quote'].split('\n')[0].strip())
        for line in lines:
            if line['text'].strip() and line['text'].strip() in names:headings.append((line['start'],definition['id']))
    headings.sort();ranges=[]
    for index,(start,key) in enumerate(headings):ranges.append((start,headings[index+1][0] if index+1<len(headings) else len(content),key))
    if headings:ranges.append((0,headings[0][0],'summary'))
    boilerplate=set()
    for section in template['sections']:
        for owner in [section,*section['merchants']]:
            if section['mode']=='permanent' or section['merchants']:
                for field in ('text','after_text'):
                    boilerplate.update(normal(s) for s in owner[field].splitlines() if s.strip())
            boilerplate.add(normal(owner['heading']))
    result=[]
    uncertain_permanent=any(s['mode']=='permanent' and not any(a['id']==s['id'] and a.get('status')=='confirmed' for a in anchors) and not any(r[2]==s['id'] for r in ranges)
                            and any(len(fragment.strip())>8 and fragment.strip() in content for a in anchors if a['id']==s['id'] for fragment in a.get('quote','').splitlines()) for s in template['sections'])
    for line in lines:
        confirmed=[a for a in anchors if a.get('status')=='confirmed' and a['start']<=line['start']<a['end']]
        inferred=[r[2] for r in ranges if r[0]<=line['start']<r[1]]
        key=confirmed[0]['id'] if confirmed else inferred[0] if len(inferred)==1 else ''
        section=definitions.get(key,{})
        excluded=section.get('mode')=='permanent' or key in {'hashtags','videos','chapters'} or normal(line['text']) in boilerplate or bool(re.match(r'\s*(?:#|\d{1,2}:\d{2})',line['text']))
        eligible=not excluded and (bool(key) or not uncertain_permanent)
        result.append({**line,'section_id':key,'eligible':eligible})
    return result


def product_label(label):
    label=re.sub(r'^[\W_]+','',label).strip().rstrip(':：-– ').strip()
    key=normal(label)
    if not key or key in GENERIC or len(label)>160 or '://' in label or '#' in label:return ''
    if re.search(r'\b(boutique|soutien|instagram|discord|ko fi|abonne|chaine|communaute)\b',key):return ''
    return label


def matches(query, items):
    q=set(normal(query).split())-STOP
    if normal(query) in GENERIC or len(q)<2:return []
    result=[]
    for item in items.values():
        name=normal(item['name']);words=set(name.split())-STOP
        if (words & ACCESSORIES)-q:continue
        references={w for w in q if re.search(r'\d',w)}
        if references and not references<=words:continue
        overlap=len(q&words)/max(1,len(q))
        if q<=words or (overlap>=.66 and len(q&words)>=2):
            result.append({'link_id':item['id'],'confidence':'exact' if normal(query)==name else 'possible'})
    return sorted(result,key=lambda r:(r['confidence']!='exact',r['link_id']))[:30]


def analyze(db, document, origin):
    content=document['text'];template=document['template_snapshot'];items,tokens,aliases=catalogue(db,origin,template)
    source_host=urlsplit(origin).netloc.casefold();lines=scopes(content,document['sections'],template)
    occurrences=urls(content);groups={};products={};proposals=[];permanent_ids=set()
    for s in template['sections']:
        for owner in [s,*s['merchants']]:permanent_ids.update(b['link_id'] for b in owner['links'] if b['link_id'])
    def add_product(label,line,manual_id=None):
        label=product_label(label)
        if not label:return None
        key=manual_id or identity('product',normal(label))
        if key not in products:products[key]={'id':key,'name':label,'manual':bool(manual_id),'position':line['start'],'evidence':[], 'matches':matches(label,items)}
        span={'start':line['start'],'end':line['end']}
        if span not in products[key]['evidence'] and not manual_id:products[key]['evidence'].append(span)
        return key
    # Draft-owned explicit references, not a second catalogue.
    for ref in document.get('products',[]):
        if ref.get('kind')=='manual-reference':add_product(ref['query'],{'start':len(content),'end':len(content)},ref['id'])
    for occurrence in occurrences:
        raw=occurrence['url'];key=identity('url',raw)
        line=next((l for l in lines if l['start']<=occurrence['start']<=l['end']),{'text':'','start':0,'end':0,'eligible':False,'section_id':''})
        if key not in groups:
            parsed=urlsplit(absolute(raw));local=parsed.netloc.casefold()==source_host
            known=(tokens.get(parsed.path[4:]) if parsed.path.startswith('/go/') else aliases.get(parsed.path[1:])) if local else None
            found=[]
            if known and known.get('link_id'):found=[{'link_id':known['link_id'],'confidence':'exact'}]
            elif not local:
                try:target=tracked_links.canonical_destination(absolute(raw))
                except (ValueError,UnicodeError):target=None
                for item in items.values():
                    try:equal=target is not None and any(tracked_links.canonical_destination(url)==target for url in (item['url'],item['original_url']) if url)
                    except (ValueError,UnicodeError):equal=False
                    if equal:found.append({'link_id':item['id'],'confidence':'exact'})
            label=product_label(content[line['start']:occurrence['start']])
            is_amazon=occurrence['kind']=='amazon' or any(kind(items[m['link_id']]['url'])=='amazon' for m in found)
            groups[key]={'id':key,'url':raw,'kind':'links' if known else occurrence['kind'],'amazon':is_amazon,'known':known,
                         'matches':found,'occurrences':[],'label':label,'product_id':None}
        group=groups[key];group['occurrences'].append({**occurrence,'section_id':line['section_id']})
        label=product_label(content[line['start']:occurrence['start']])
        if not label and len(group['matches'])==1:label=items[group['matches'][0]['link_id']]['name']
        commercial=occurrence['kind'] in {'amazon','domadoo'} or bool(group['matches']) or bool(re.search(r'\b\w*[A-Za-z]\w*\d[\w-]*\b',label))
        video=occurrence['kind']=='youtube' or any(kind(items[m['link_id']]['url'])=='youtube' for m in group['matches'])
        if commercial and line['eligible'] and not video and not (group['known'] or {}).get('campaign_id') and not any(m['link_id'] in permanent_ids for m in group['matches']):
            group['product_id']=add_product(label,line) or group['product_id']
    for line in lines:
        if not line['eligible']:continue
        # Names must occur literally in video-specific text, never in a URL slug.
        prose=line['text']
        for occurrence in reversed([o for o in occurrences if line['start']<=o['start']<line['end']]):
            prose=prose[:occurrence['start']-line['start']]+' '+prose[occurrence['end']-line['start']:]
        prose=re.sub(r'(?<!\w)#[\w-]+',' ',prose)
        normalized=' '+normal(prose)+' '
        for item in items.values():
            if item['id'] not in permanent_ids and ' '+normal(item['name'])+' ' in normalized and len(normal(item['name']).split())>=2:add_product(item['name'],line)
        # Conservative explicit brand/model syntax. Generic technology words alone
        # cannot trigger this rule; unrecognised references can be added manually.
        for hit in re.finditer(r'\b[A-Z][A-Z0-9]{2,}(?:[ \t]+[A-Z][\w-]*){1,4}',prose):
            label=hit.group()
            if any(re.search(r'[a-z][A-Z]|[A-Z]{2}[a-z]|\d|[A-Z]-[A-Z]',w) for w in label.split()[1:]):add_product(label,line)
    # Existing URL operations are selected. Additions and moves are independent.
    for group in groups.values():
        found=group['matches'];item=items[found[0]['link_id']] if len(found)==1 else None
        preferred=(group['known'] or {}).get('source_id','')
        pubs=[p for p in (item or {}).get('publications',[]) if p['youtube'] and p['active']]
        if not preferred and len(pubs)==1:preferred=pubs[0]['source_id']
        title=url_inspection.suggest_local_title(absolute(group['url']),known_title=(item or {}).get('name',''),written_title=group['label'])
        proposals.append({'id':group['id'],'kind':'reuse','url_id':group['id'],'product_id':group['product_id'],
                          'selected':True,'link_id':item['id'] if item else '', 'source_id':'' if group['amazon'] else preferred,
                          'label':title['title'],'title_engine':title['engine'], 'matches':found,'amazon':group['amazon'],
                          'blocked_reason':'Ce lien LinKs mène à Amazon. Confirmez une URL affiliée directe dans le texte ; aucune redirection Amazon n’est préparée.' if group['amazon'] and group['kind']=='links' else ''})
        destination_kind=kind(item['url']) if item else group['kind']
        target='videos' if destination_kind=='youtube' else 'affiliate' if destination_kind in {'amazon','domadoo'} or (item or {}).get('partner_id') else None
        for section in template['sections']:
            bindings=[b for owner in [section,*section['merchants']] for b in owner['links']]
            if any(m['link_id'] in {b['link_id'] for b in bindings} for m in found) or any(b['reference_url']==absolute(group['url']) for b in bindings):target=section['id']
        if target in {s['id'] for s in template['sections']} and any(o['section_id'] and o['section_id']!=target for o in group['occurrences']):
            proposals.append({'id':identity('move',group['id']+target),'kind':'move','url_id':group['id'],'product_id':group['product_id'],'target_section':target,'selected':False,'label':'Déplacer vers '+next((s['name'] for s in template['sections'] if s['id']==target),target),'matches':[],'link_id':'','source_id':'','amazon':group['amazon']})
    present={m['link_id'] for g in groups.values() for m in g['matches']}
    for product in products.values():
        merchants={}
        for match in product['matches']:
            item=items[match['link_id']]
            if item['id'] in present:continue
            merchants.setdefault(item['merchant'],[]).append(match)
        for merchant,found in merchants.items():
            item=items[found[0]['link_id']] if len(found)==1 else None
            title=url_inspection.suggest_local_title(item['url'] if item else '',known_title=item['name'] if item else product['name'])
            proposals.append({'id':identity('add',product['id']+merchant),'kind':'add','product_id':product['id'],'merchant':merchant,'selected':False,
                              'link_id':item['id'] if item and found[0]['confidence']=='exact' else '', 'source_id':'','label':title['title'],'title_engine':title['engine'],'matches':found,'amazon':any(kind(items[m['link_id']]['url'])=='amazon' for m in found)})
    used={m['link_id'] for owner in [*groups.values(),*products.values()] for m in owner['matches']}
    return {'urls':list(groups.values()),'products':sorted(products.values(),key=lambda p:(p['position'],p['id'])),
            'proposals':proposals,'catalogue':[item for key,item in items.items() if key in used],'partners':[{'id':p['id'],'name':p['name']} for p in affiliate_partners.rows(db)],
            'warnings':['Confirmez les sections ambiguës pour analyser tous les passages propres à la vidéo.'] if any(a.get('status')!='confirmed' for a in document['sections']) else []}
