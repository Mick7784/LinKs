const {test}=require('node:test'),assert=require('node:assert/strict');
require('../admin/statistics-workspace.js');
const {filter,aggregate,percentages,shift}=globalThis.LinksStatisticsModel;
test('canonical homonyms and filtered origins keep exact totals',()=>{
 const items=[{id:'a',name:'Identique',sources:{youtube:8,instagram:3,discord:1}},{id:'b',name:'Identique',sources:{youtube:2,unknown:4}}];
 assert.equal(filter(items).length,2);assert.equal(filter(items,'b')[0].id,'b');
 assert.deepEqual({...aggregate(filter(items,'','youtube'))},{youtube:10});
 assert.equal(filter(items,'','youtube')[0].total,8);assert.equal(filter(items,'missing').length,0);
 assert.equal(filter(items,'','p:youtube',key=>key)[0].total,8);
});
test('legend percentages sum to 100 and empty is never fabricated',()=>{
 assert.deepEqual(percentages({a:1,b:1,c:1}),{a:34,b:33,c:33});assert.deepEqual(percentages({}),{});assert.deepEqual(percentages({unknown:12}),{unknown:100});
});
test('calendar navigation crosses DST without skipping a local date',()=>{
 assert.equal(shift('2026-03-29',1),'2026-03-30');assert.equal(shift('2026-10-25',-1),'2026-10-24');
});
test('10,000 items remain searchable and fully counted',()=>{
 const data=Array.from({length:10000},(_,i)=>({id:'link-'+i,name:'Link '+i,sources:{youtube:1}}));
 assert.equal(filter(data).length,10000);assert.equal(aggregate(filter(data)).youtube,10000);assert.equal(filter(data,'link-9999')[0].id,'link-9999');
});
