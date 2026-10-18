const {test}=require('node:test'),assert=require('node:assert/strict');
require('../admin/collection.js');
test('shared collection filters details, sorts deterministically and bounds pages',()=>{
 const rows=Array.from({length:503},(_,i)=>({name:`Lien ${String(i).padStart(3,'0')}`,total:i,details:[i%2?'YouTube':'Instagram']}));
 const result=StudioCollection.select(rows,{query:'youtube',page:100,pageSize:20});
 assert.equal(result.total,251);assert.equal(result.page,12);assert.equal(result.rows.length,11);assert.equal(result.rows[0].total,21);
 assert.equal(StudioCollection.select(rows,{query:'Lien 002',sort:'name'}).rows[0].total,2);
 assert.equal(rows[0].total,0,'input must remain unchanged');
 assert.deepEqual(StudioCollection.select(rows,{query:'absent'}),{rows:[],total:0,pages:1,page:0});
});
