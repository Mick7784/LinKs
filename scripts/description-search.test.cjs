const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const context={window:{},structuredClone,AbortController,setTimeout,clearTimeout,URL};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../admin/description-search.js'),'utf8'),context);
const {Panel,stored,merge}=context.window.LinksDescriptionSearch;
const products=[{id:'hub',name:'SMLIGHT SMHub Nano MG24'},{id:'kit',name:'Kit CPL'}];
const response=query=>({query,merchants:{domadoo:{query,status:'found',results:[{id:'one',url:'https://www.domadoo.fr/fr/1-hub.html'}]},amazon:{query,status:'amazon_link_required',results:[]}}});
function setup(request){const editor={doc:{id:'draft',text:'Original 😀',selections:{},manual_order:['kit','hub']},paint(){},changed(){this.changes=(this.changes||0)+1}};const analysis={editor,request,result:{products},input:()=>({text:editor.doc.text})};return {panel:new Panel(analysis),editor,analysis}}

test('global search is explicit, skips resolved products and isolates individual retries',async()=>{
 const calls=[];const {panel,editor}=setup(async(path,body)=>{calls.push(body);return response(body.query)});
 assert.equal(calls.length,0);await panel.all();assert.equal(calls.length,2);
 panel.merchantChange(products[0],'amazon',{prepared:{url:'https://amzn.to/exact'},selected:true,label:'Mon choix'});
 panel.merchantChange(products[1],'amazon',{status:'no_match'});
 await panel.all();assert.equal(calls.length,2);
 const other=JSON.stringify(stored(editor.doc).kit);await panel.search(products[0],true);assert.equal(calls.length,3);
 assert.equal(JSON.stringify(stored(editor.doc).kit),other);assert.equal(stored(editor.doc).hub.merchants.amazon.selected,true);
 assert.equal(stored(editor.doc).hub.merchants.amazon.label,'Mon choix');assert.equal(editor.doc.text,'Original 😀');assert.deepEqual(editor.doc.manual_order,['kit','hub']);
});
test('merchant errors preserve result snapshots, preparation and choices',()=>{
 const previous={results:[{id:'one'}],prepared:{url:'exact'},selected:true,label:'Corrigé',source_id:'historic'};
 const value=merge(previous,{status:'error',results:[],message:'Unavailable'});
 assert.equal(value.results,previous.results);assert.equal(value.prepared,previous.prepared);assert.equal(value.source_id,'historic');assert.equal(value.label,'Corrigé');
});
test('global retry skips a resolved merchant independently',async()=>{
 const calls=[];const {panel,editor}=setup(async(path,body)=>{calls.push(body);return response(body.query)});
 panel.merchantChange(products[0],'domadoo',{status:'found',results:[{id:'kept'}],selected:false});
 await panel.search(products[0]);assert.deepEqual([...calls[0].merchants],['amazon']);assert.equal(stored(editor.doc).hub.merchants.domadoo.results[0].id,'kept');
});
test('stale search cannot replace newer query results or recent choices',async()=>{
 let resolve;const {panel,editor}=setup((path,body)=>body.query==='old'?new Promise(r=>resolve=r):Promise.resolve(response(body.query)));
 panel.change(products[0],s=>({...s,query:'old'}));const old=panel.search(products[0],true);
 panel.change(products[0],s=>({...s,query:'new'}));await panel.search(products[0],true);
 panel.merchantChange(products[0],'domadoo',{label:'Récent 😀',selected:true});resolve(response('old'));await old;
 assert.equal(stored(editor.doc).hub.merchants.domadoo.query,'new');assert.equal(stored(editor.doc).hub.merchants.domadoo.label,'Récent 😀');
});
test('removed product and changed draft cannot receive late search results',async()=>{
 let resolve;const {panel,editor,analysis}=setup(()=>new Promise(r=>resolve=r));const pending=panel.search(products[0]);analysis.result.products=[];resolve(response('old'));await pending;
 assert.equal(stored(editor.doc).hub.merchants.domadoo.status,'searching');
});
test('preparation preserves an edited label while pending and starts unchecked',async()=>{
 let resolve;const {panel,editor}=setup(()=>new Promise(r=>resolve=r));const pending=panel.prepare(products[0],'amazon','https://amzn.to/exact');
 panel.merchantChange(products[0],'amazon',{label:'Saisi pendant la requête'});
 resolve({url:'https://amzn.to/exact',original_url:'https://amzn.to/exact',link_id:'',label:'Generated',sources:[],placements:[{section_id:'affiliate',merchant_id:'amazon'}]});await pending;
 const value=stored(editor.doc).hub.merchants.amazon;assert.equal(value.label,'Saisi pendant la requête');assert.equal(value.selected,false);assert.equal(value.source_id,'');
});
test('editing pasted URL invalidates a delayed preparation response',async()=>{
 let resolve;const {panel,editor}=setup(()=>new Promise(r=>resolve=r));const pending=panel.prepare(products[0],'amazon','https://amzn.to/old');
 panel.merchantChange(products[0],'amazon',{url_input:'https://link.amazon/new?tag=exact'});resolve({url:'https://amzn.to/old'});await pending;
 assert.equal(stored(editor.doc).hub.merchants.amazon.prepared,undefined);assert.equal(stored(editor.doc).hub.merchants.amazon.url_input,'https://link.amazon/new?tag=exact');
});
