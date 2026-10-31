"""Explicit merchant preparation over the existing services. No catalogue writes.

Search providers return disposable draft suggestions. Domadoo currently requires
the assisted provider: its public robots rules exclude automated search pages.
Neither provider uses the reporting connector, browser sessions or redirects.
"""
from urllib.parse import urlencode, urlsplit

import affiliate_partners
import description_analysis as analysis
import tracked_links
import url_inspection

MERCHANTS = ('domadoo', 'amazon')
STATES = {'search_required', 'amazon_link_required', 'found', 'existing', 'no_match', 'error', 'searching'}


def search_url(merchant, query):
    return ('https://www.domadoo.fr/fr/recherche?' + urlencode({'s': query}) if merchant == 'domadoo'
            else 'https://www.amazon.fr/s?' + urlencode({'k': query}))


def merchant_search(merchant, query):
    """Provider boundary for a future authorized product feed; assisted today."""
    return {'status': 'amazon_link_required' if merchant == 'amazon' else 'search_required', 'results': [],
            'message': 'Recherche assistée : ouvrez le site et collez la fiche choisie.' if merchant == 'domadoo'
            else 'Générez votre lien affilié avec les outils officiels Amazon, puis collez-le ici.'}


def valid_url(value, merchant):
    # Validate a copy, keep the supplied bytes (including bare short URLs).
    if not isinstance(value,str) or len(value)>2000 or not affiliate_partners.http_url(analysis.absolute(value)) or analysis.kind(value)!=merchant:return False
    parsed=urlsplit(analysis.absolute(value));host=parsed.hostname.lower().rstrip('.')
    if merchant=='amazon':
        domains=('amazon.fr','amazon.com','amazon.co.uk','amazon.de','amazon.es','amazon.it','amazon.nl','amazon.com.be','amazon.pl','amazon.se','amazon.ie','amazon.ca','amazon.com.mx','amazon.com.br','amazon.co.jp','amazon.in','amazon.com.au','amazon.sg','amazon.ae','amazon.sa','amazon.com.tr','amazon.eg','amazon.co.za')
        if host not in {'amzn.to','link.amazon'} and not any(host==d or host.endswith('.'+d) for d in domains):return False
        return parsed.path not in {'','/','/s','/s/'}
    return parsed.path.rstrip('/') not in {'','/fr','/fr/recherche','/en','/en/search'}


def validate_state(state):
    from descriptions import ident, text, flag, sequence
    if not isinstance(state, dict) or set(state) != {'version', 'products'} or type(state['version']) is not int or state['version'] != 1:
        raise ValueError('Recherches marchandes invalides.')
    products = state['products']
    if not isinstance(products, dict) or len(products) > 100:raise ValueError('Trop de recherches marchandes.')
    for key, product in products.items():
        ident(key)
        if not isinstance(product, dict) or set(product) != {'query', 'merchants'}:raise ValueError('Recherche produit invalide.')
        text(product, 'query', 160)
        if not isinstance(product['merchants'], dict) or set(product['merchants']) - set(MERCHANTS):raise ValueError('Marchand invalide.')
        for merchant, value in product['merchants'].items():
            if not isinstance(value, dict) or set(value) - {'status','query','results','message','url_input','prepared','selected','label','link_id','source_id','section_id','merchant_id'}:raise ValueError('État marchand invalide.')
            if value.get('status', 'search_required') not in STATES:raise ValueError('État de recherche invalide.')
            for field, limit in [('query',160),('message',1000),('url_input',2000),('label',160)]:text(value,field,limit)
            flag(value,'selected')
            for field in ('link_id','source_id','section_id','merchant_id'):
                if value.get(field):ident(value[field])
            for result in sequence(value.get('results',[]),30):
                if set(result) != {'id','title','reference','url','link_id','confidence'}:raise ValueError('Résultat marchand invalide.')
                ident(result.get('id'));text(result,'title',160);text(result,'reference',160);text(result,'link_id',80);text(result,'confidence',30)
                if not valid_url(result.get('url'),merchant):raise ValueError('URL marchande invalide.')
            prepared = value.get('prepared')
            if prepared is not None:
                if not isinstance(prepared,dict) or set(prepared) != {'original_url','url','partner_id','mode','label','link_id','duplicates','sources','placements'}:raise ValueError('Préparation invalide.')
                if not valid_url(prepared.get('original_url'),merchant) or not valid_url(prepared.get('url'),merchant):raise ValueError('Destination invalide.')
                if prepared['mode'] != ('direct' if merchant=='amazon' else 'tracked_pending'):raise ValueError('Mode invalide.')
                if merchant=='amazon' and (prepared['url']!=prepared['original_url'] or prepared['partner_id']):raise ValueError('L’URL Amazon doit rester intacte.')
                text(prepared,'label',160);text(prepared,'partner_id',80);text(prepared,'link_id',80)
                for dup in sequence(prepared.get('duplicates'),30):
                    if set(dup)!={'id','name','url','archived','enabled'}:raise ValueError('Doublon invalide.')
                    ident(dup.get('id'));text(dup,'name',160);text(dup,'url',2000)
                for source in sequence(prepared.get('sources'),100):
                    if set(source)!={'id','name','url'}:raise ValueError('Source invalide.')
                    ident(source.get('id'));text(source,'name',160);text(source,'url',2000)
                for place in sequence(prepared.get('placements'),100):
                    if set(place)!={'section_id','merchant_id','name'}:raise ValueError('Emplacement invalide.')
                    ident(place.get('section_id'));ident(place.get('merchant_id'));text(place,'name',400)


def context(db, key, data, origin):
    import descriptions as d
    if not isinstance(data,dict):raise ValueError('Requête marchande invalide.')
    result=d.analyze_draft(db,key,data.get('document'),origin)
    product=next((p for p in result['products'] if p['id']==data.get('product_id')),None)
    if not product:raise ValueError('Cette référence n’est plus présente dans la description.')
    document=d.editor_document(d.get(db,d.TABLES[1],key))
    items,_,_=analysis.catalogue(db,origin,document['template_snapshot'])
    return product,result,document,items


def candidate(item, confidence='possible'):
    return {'id':item['id'],'title':url_inspection.suggest_local_title(item['url'],known_title=item['name'])['title'],
            'reference':item['name'],'url':item['url'],'link_id':item['id'],'confidence':confidence}


def search_product(db,key,data,origin):
    from descriptions import text
    product,result,document,items=context(db,key,data,origin)
    query=text(data,'query',160,True)
    merchants=data.get('merchants',list(MERCHANTS))
    if not isinstance(merchants,list) or not merchants or len(merchants)>2 or any(m not in MERCHANTS for m in merchants) or len(set(merchants))!=len(merchants):raise ValueError('Marchands de recherche invalides.')
    matches=analysis.matches(query,items)
    response={}
    for merchant in merchants:
        found=[candidate(items[m['link_id']],m['confidence']) for m in matches
               if valid_url(items[m['link_id']]['url'],merchant) and not items[m['link_id']]['archived'] and items[m['link_id']]['enabled']]
        # Exact destinations explicitly present in this product's text are useful
        # even when its written name differs from the catalogue title.
        for url in result['urls']:
            if url['product_id']!=product['id']:continue
            if url['kind']==merchant and valid_url(url['url'],merchant) and not any(c['url']==url['url'] for c in found):
                found.append({'id':url['id'],'title':url['label'] or product['name'],'reference':product['name'],
                              'url':url['url'],'link_id':'','confidence':'explicit_url'})
        if found:
            response[merchant]={'status':'existing' if any(c['link_id'] for c in found) else 'found','results':found[:30],
                                'message':'Choisissez la référence exacte ; aucune sélection automatique.'}
        else:
            try:
                provider=merchant_search(merchant,query)
                if provider.get('status') not in STATES or not isinstance(provider.get('results'),list):raise ValueError('Réponse marchande invalide.')
                rows=[]
                for item in provider['results'][:30]:
                    if not valid_url(item.get('url'),merchant):raise ValueError('Destination marchande invalide.')
                    title=text(item,'title',160,True);reference=text(item,'reference',160)
                    rows.append({'id':analysis.identity('merchant',item['url']),'url':item['url'],'title':title,'reference':reference,'link_id':'','confidence':'possible'})
                response[merchant]={'status':'found' if rows else provider['status'],'results':rows,'message':text(provider,'message',1000)}
            except (OSError,ValueError,TypeError,KeyError):
                response[merchant]={'status':'error','results':[],'message':'Erreur de recherche. Vos choix sont conservés ; réessayez ou ouvrez le site.'}
        response[merchant].update(query=query)
    return {'product_id':product['id'],'query':query,'merchants':response}


def prepare_link(db,key,data,origin):
    from descriptions import text
    product,result,document,items=context(db,key,data,origin)
    merchant=data.get('merchant');raw=text(data,'url',2000,True)
    if merchant not in MERCHANTS or not valid_url(raw,merchant):raise ValueError('Collez une URL valide du marchand choisi, sans espaces ajoutés.')
    chosen=text(data,'link_id',80)
    if chosen and (chosen not in items or items[chosen]['archived'] or not items[chosen]['enabled'] or items[chosen]['url']!=raw):
        raise ValueError('La fiche choisie a changé ou n’est plus disponible. Recherchez à nouveau.')
    if merchant=='amazon':
        final=raw;partner=''
        duplicates=tracked_links.duplicate_destinations(db,analysis.absolute(raw))
    else:
        duplicates=tracked_links.duplicate_destinations(db,raw)
        if duplicates:
            # A catalogue destination is immutable here, even if its affiliation
            # differs from today's partner rule. Never propose a silent edit.
            final=raw;partner=items[chosen]['partner_id'] if chosen else ''
        else:
            partner=affiliate_partners.detect(db,raw)
            if not partner:raise ValueError('Configurez le partenaire Domadoo existant avant de préparer ce lien.')
            preview=affiliate_partners.preview_tracked(db,{'url':raw,'partner_id':partner})
            final=preview['url'];duplicates=tracked_links.duplicate_destinations(db,final)
        if analysis.kind(final)!='domadoo':raise ValueError('La règle du partenaire doit conserver une destination Domadoo.')
    active=[i for i in duplicates if i['enabled'] and not i['archived']]
    link_id=chosen or (active[0]['id'] if len(active)==1 else '')
    known=items.get(link_id)
    title=url_inspection.suggest_local_title(analysis.absolute(raw),known_title=known['name'] if known else product['name'],written_title=text(data,'label',160))['title']
    sources=[]
    if merchant!='amazon':
        if known:
            sources=[{'id':p['source_id'],'name':p['source_name'],'url':p['url']} for p in known['publications'] if p['active'] and p['youtube']]
        # Source choices are existing records only; an absent publication is
        # explicitly pending, never allocated here.
        if not sources:
            ids=set(tracked_links.platform_source_ids(db,'youtube'))
            sources=[{'id':s['id'],'name':s['name'],'url':''} for s in db.execute('SELECT id,name FROM tracking_sources WHERE active=1')
                     if s['id'] in ids or s['name'] in {'YouTube','YouTube Description','YouTube Post'}]
    placements=[]
    for section in document['template_snapshot']['sections']:
        for sub in section['merchants']:
            if sub['id']==merchant or (partner and sub['partner_id']==partner):
                placements.append({'section_id':section['id'],'merchant_id':sub['id'],'name':section['name']+' / '+sub['heading']})
    return {'original_url':raw,'url':final,'partner_id':partner,'mode':'direct' if merchant=='amazon' else 'tracked_pending',
            'label':title,'link_id':link_id,'duplicates':duplicates[:30],'sources':sources[:100],'placements':placements[:100]}
