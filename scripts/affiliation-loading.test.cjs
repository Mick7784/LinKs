const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../admin/affiliation.js'),'utf8').match(/async function load\([\s\S]*?\n }/)[0];
function context(){const ctx=vm.createContext({});vm.runInContext(`
let loadVersion=0,timer=null,initialRange=false,pollError=false,tab='overview';
let model={amount:100,accounts:[{id:'a',snapshot:{id:1},running:false}]};
let displayed=100,renders=0,queue=[];
const range=()=>'',clearTimeout=()=>{},setTimeout=()=>0;
const request=()=>new Promise(resolve=>queue.push(resolve));
const render=()=>{renders++;displayed=model.amount},renderContent=render;
const refreshSyncState=()=>{},selected=()=>model.accounts[0];
const updateAmazonPortalState=()=>{},loadRuns=()=>{},loadSales=()=>{};
const host={classList:{contains:()=>true}},say=()=>{};
`+source,ctx);return ctx}
for(const order of ['poll-first','navigation-first'])test('navigation renders despite concurrent poll: '+order,async()=>{
 const ctx=context();await vm.runInContext(`(async()=>{
 const navigation=load();const polling=load({poll:true});
 ${order==='poll-first'?`queue[1]({amount:200,accounts:model.accounts});await polling;queue[0]({amount:200,accounts:model.accounts});await navigation;`:`queue[0]({amount:200,accounts:model.accounts});await navigation;queue[1]({amount:200,accounts:model.accounts});await polling;`}
 })()`,ctx);assert.equal(vm.runInContext('displayed',ctx),200);assert.equal(vm.runInContext('renders',ctx),1);
});
test('unchanged ordinary polling preserves the current form',async()=>{const ctx=context();await vm.runInContext('(async()=>{const p=load({poll:true});queue[0](model);await p})()',ctx);assert.equal(vm.runInContext('renders',ctx),0)});
