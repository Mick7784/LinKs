const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const store=new Map(),context={window:{},structuredClone,setTimeout,clearTimeout,AbortController,Uint32Array,localStorage:{get length(){return store.size},key:i=>[...store.keys()][i],getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../admin/description-workflow.js'),'utf8'),context);const {diff,Controller}=context.window.LinksDescriptionWorkflow;
test('comparison preserves exact lines, Unicode and final newlines without HTML interpretation',()=>{
 for(const [before,after] of [['😀 Intro\nhttps://amzn.to/Exact?x=%2b\n','😀 Intro\nhttps://link.amazon/New?tag=21\n'],['<script>text</script>\n\n','\nNew\n'],['a\nb','b\na']]){
  const rows=diff(before,after);assert.equal(rows.filter(x=>x.left!==undefined).map(x=>x.left).join('\n'),before);assert.equal(rows.filter(x=>x.right!==undefined).map(x=>x.right).join('\n'),after);
 }
});
function editor(){return {instance:'instance',doc:{id:'draft',revision:1,text:'Ancien'},writer:'one',generation:0,ack:0,saving:false,blocked:false,dirty(){return this.generation!==this.ack},persist(){},paint(){},key(){return 'editor-key'},remember(){this.remembered=true},writeArea(){},forgetRecovery(){}}}
test('a delayed application response cannot overwrite recent typing',async()=>{
 store.clear();let done;const e=editor(),flow=new Controller(e,()=>new Promise(r=>done=r));flow.paint=()=>{};
 const pending=flow.execute('drafts/draft/apply',{mutation_id:'one'});e.doc.text='Saisie récente 😀';e.generation++;
 done({document:{id:'draft',revision:2,text:'Texte appliqué'},results:[]});await pending;
 assert.equal(e.doc.text,'Saisie récente 😀');assert(e.blocked);assert.equal(store.size,0);
});
test('lost response retains the exact request for idempotent retry',async()=>{
 store.clear();const e=editor(),flow=new Controller(e,async()=>{throw Error('Network')});flow.paint=()=>{};
 const body={mutation_id:'stable',expected_revision:1,plan_hash:'plan'};await assert.rejects(flow.execute('drafts/draft/apply',body));
 const pending=flow.pending();assert.equal(pending.length,1);assert.deepEqual(JSON.parse(JSON.stringify(pending[0].value.request)),body);assert(e.blocked);
 flow.request=async(path,data)=>{assert.equal(data.mutation_id,'stable');return {document:{id:'draft',revision:2,text:'Véritable URL'},results:[],replayed:true}};
 await flow.execute(pending[0].value.path,pending[0].value.request,pending[0].key,pending[0].value);assert.equal(e.doc.text,'Véritable URL');assert(!e.blocked);assert.equal(store.size,0);assert(e.remembered);
});
test('a stale confirmed plan is discarded without replaying a mutation',async()=>{
 store.clear();const e=editor(),flow=new Controller(e,async()=>{throw Object.assign(Error('Conflict'),{status:409})});flow.paint=()=>{};
 await assert.rejects(flow.execute('drafts/draft/apply',{mutation_id:'conflict'}));assert.equal(store.size,0);assert.equal(e.doc.text,'Ancien');assert(e.blocked);
});
