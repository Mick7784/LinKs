const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const context={window:{},structuredClone};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../admin/description-analysis.js'),'utf8'),context);
const {effective,ordered}=context.window.LinksDescriptionAnalysis;
const result={catalogue:[{id:'one',enabled:true,archived:false,publications:[{source_id:'old-youtube',active:true}]}],products:[{id:'a',position:0},{id:'b',position:12}],urls:[],proposals:[]};
const proposal={id:'url-stable',kind:'reuse',selected:true,link_id:'one',source_id:'old-youtube',matches:[{link_id:'one'}],label:'Initial',product_id:'a'};
test('current manual decisions win over refreshed suggestions without changing stored choices',()=>{
 const doc={selections:{description_analysis:{'url-stable':{selected:false,label:'Mon intitulé 😀',source_id:'old-youtube',product_id:'b'}}}};
 const before=JSON.stringify(doc),resolved=effective({...proposal,label:'New catalogue title'},result,doc);
 assert.equal(resolved.selected,false);assert.equal(resolved.label,'Mon intitulé 😀');assert.equal(resolved.product_id,'b');assert.equal(resolved.source_id,'old-youtube');assert.equal(JSON.stringify(doc),before);
 assert.equal(effective({...proposal,id:'move',kind:'move',url_id:'url-stable'},result,doc).product_id,'b');
});
test('only obsolete associations become inactive, decisions stay available for undo',()=>{
 const doc={selections:{description_analysis:{'url-stable':{selected:true,link_id:'missing'}}}};
 const value=effective(proposal,result,doc);assert.equal(value.selected,false);assert(value.errors.length);assert.equal(doc.selections.description_analysis['url-stable'].selected,true);
 const other=effective({...proposal,id:'unaffected'},result,doc);assert.equal(other.selected,true);assert.equal(other.errors.length,0);
});
test('obsolete source and revoked aliases never stay active',()=>{
 assert.equal(effective(proposal,{...result,catalogue:[{...result.catalogue[0],publications:[]}]},{selections:{}}).selected,false);
 assert.equal(effective({...proposal,url_id:'u'},{...result,urls:[{id:'u',known:{revoked:true}}]},{selections:{}}).selected,false);
 assert.equal(effective({...proposal,amazon:true,blocked_reason:'Direct URL required'},result,{selections:{}}).selected,false);
 assert.equal(effective({...proposal,amazon:true},result,{selections:{}}).source_id,'');
});
test('manual order survives reordered discoveries and appends only new references',()=>{
 const doc={manual_order:['b','gone','a']};const values=ordered({...result,products:[{id:'c',position:0},...result.products]},doc);
 assert.equal(values.map(p=>p.id).join(','),'b,a,c');assert.equal(doc.manual_order.join(','),'b,gone,a');
});
test('new merchant and movement defaults remain unchecked',()=>{
 assert.equal(effective({...proposal,kind:'add',selected:false},result,{selections:{}}).selected,false);
 assert.equal(effective({...proposal,kind:'move',selected:false},result,{selections:{}}).selected,false);
});
