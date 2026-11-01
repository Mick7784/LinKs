const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function element(){return {isConnected:true,children:[],dataset:{},style:{},classList:{add(){}},append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items},setAttribute(k,v){this[k]=v},addEventListener(k,fn){this[k]=fn},setSelectionRange(){}}}
function setup(api){
 const timers=new Map(),storage=new Map([['existing-recovery','untouched']]),crypto={getRandomValues:require('node:crypto').webcrypto.getRandomValues.bind(require('node:crypto').webcrypto)};
 const window={addEventListener(){},DescriptionSections:{points:s=>Array.from(s),toUTF16:(s,i)=>i},LinksDescriptionAnalysis:{Panel:class{schedule(){}render(){}}},LinksDescriptionWorkflow:{Controller:class{schedule(){}paint(){}mount(){}}}};
 const context={window,crypto,api,structuredClone,AbortController,document:{createElement:element},localStorage:{get length(){return storage.size},key:i=>[...storage.keys()][i],getItem:k=>storage.get(k)},setTimeout(fn,ms){const id={};timers.set(id,{fn,ms});return id},clearTimeout(id){timers.delete(id)}};
 for(const file of ['uuid.js','description-editor.js'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../admin',file),'utf8'),context);
 return {context,window,crypto,timers,storage,host:element(),mount:window.LinksDescriptionEditor.mount};
}
const response=id=>({instance_id:'instance',document:{id,title:'Brouillon existant',text:'Texte 😀 intact',revision:7,sections:[],template_snapshot:{sections:[]},problems:[]}});
function failure(host){assert.match(host.children[0].textContent,/Impossible de charger le brouillon/);assert.equal(host.children[0].role,'alert');assert.equal(host.children[1].textContent,'Réessayer')}
test('loads without randomUUID, retains existing revision and recovery data',async()=>{
 const s=setup(async()=>response('one'));await s.mount(s.host,'one');assert.equal(s.host.editorOwner.doc.revision,7);assert.equal(s.host.editorOwner.area.value,'Texte 😀 intact');assert.equal(s.storage.get('existing-recovery'),'untouched');assert.equal(s.timers.size,0);
 // A remount reuses the in-memory unsaved document instead of reloading it.
 s.host.editorOwner.doc.text='Saisie non enregistrée';await s.mount(s.host,'one');assert.equal(s.host.editorOwner.area.value,'Saisie non enregistrée');
});
test('missing crypto during constructor becomes an actionable error and retry works',async()=>{
 const s=setup(async()=>response('one'));s.context.crypto=undefined;await s.mount(s.host,'one');failure(s.host);assert.match(s.host.children[0].textContent,/génération sécurisée/);assert.equal(s.timers.size,0);
 s.context.crypto=s.crypto;await s.host.children[1].click();assert.equal(s.host.editorOwner.doc.id,'one');assert.equal(s.storage.get('existing-recovery'),'untouched');
});
test('synchronous and asynchronous request failures offer retry without rejected mount',async()=>{
 for(const api of [()=>{throw Error('Network')},async()=>{throw Error('Network')},async()=>{throw null}]){
  const s=setup(api);await s.mount(s.host,'one');failure(s.host);assert.equal(s.timers.size,0);s.context.api=async()=>response('one');await s.host.children[1].click();assert.equal(s.host.editorOwner.doc.id,'one');
 }
});
test('render exceptions are caught and cached state survives retry',async()=>{
 const s=setup(async()=>response('one'));const proto=s.window.LinksDescriptionWorkflow.Controller.prototype,original=proto.mount;proto.mount=()=>{throw Error('Render failed')};await s.mount(s.host,'one');failure(s.host);proto.mount=original;await s.host.children[1].click();assert.equal(s.host.editorOwner.doc.revision,7);
});
test('hung request times out and its late response cannot replace a successful retry',async()=>{
 let finish,signal;const s=setup((p,options)=>{signal=options.signal;return new Promise(resolve=>finish=resolve)}),pending=s.mount(s.host,'one');
 assert.equal([...s.timers.values()][0].ms,15000);[...s.timers.values()][0].fn();await pending;assert(signal.aborted);failure(s.host);assert.match(s.host.children[0].textContent,/serveur ne répond pas/);assert.equal(s.timers.size,0);
 s.context.api=async()=>response('one');await s.host.children[1].click();finish(response('stale'));await Promise.resolve();assert.equal(s.host.editorOwner.doc.id,'one');
});
test('out-of-order success or failure cannot replace the newly selected draft',async()=>{
 for(const fail of [false,true]){
  let finish,reject;const s=setup(()=>new Promise((r,j)=>{finish=r;reject=j})),first=s.mount(s.host,'one');s.context.api=async()=>response('two');await s.mount(s.host,'two');
  if(fail)reject(Error('Old failure'));else finish(response('one'));await first;assert.equal(s.host.editorOwner.doc.id,'two');assert.equal(s.timers.size,0);
 }
});
test('detached host is not mounted when its response arrives',async()=>{
 let finish;const s=setup(()=>new Promise(r=>finish=r)),pending=s.mount(s.host,'one');s.host.isConnected=false;finish(response('one'));await pending;assert.equal(s.host.editorOwner,null);assert.equal(s.timers.size,0);
});
