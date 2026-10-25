const {test}=require('node:test'),assert=require('node:assert/strict');
require('../admin/source-platforms.js');
const group=StudioSourcePlatforms.group;

test('historical source names group into declared platforms without losing keys or contributions',()=>{
 const sources=[{key:'post',label:'YouTube Post',total:4},{key:'description',label:'YouTube Description',total:6},{key:'story',label:'Instagram Story',total:3},{key:'bio',label:'Instagram Bio',total:7},{key:'discord',label:'Discord',total:5}];
 const before=structuredClone(sources),result=group(sources);
 assert.deepEqual(result.map(row=>[row.key,row.total]).sort(),[['discord',5],['instagram',10],['youtube',10]]);
 assert.deepEqual(result.find(row=>row.key==='youtube').sources.map(row=>row.key),['post','description']);assert.deepEqual(sources,before);assert.equal(result.reduce((n,p)=>n+p.total,0),sources.reduce((n,s)=>n+s.total,0));for(const platform of result)assert.equal(platform.total,platform.sources.reduce((n,s)=>n+s.total,0));
});

test('explicit platform metadata survives a rename and takes priority over a misleading label',()=>{
 const rows=[{key:'tracked:canonical',label:'Publication renommée',total:8},{key:'tracked:conflict',label:'YouTube Post',total:2}],metadata=[{id:'canonical',name:'Renommée',platform:'youtube',active:false,clicks:999},{id:'conflict',name:'YouTube Post',platform:'instagram'}],before=structuredClone(metadata);
 const result=group(rows,metadata);assert.equal(result.find(row=>row.key==='youtube').total,8);assert.equal(result.find(row=>row.key==='instagram').total,2);assert.deepEqual(metadata,before);
});

test('uncertain legacy story keys and unresolved sources never become Instagram from their spelling',()=>{
 const result=group([{key:'instagram-story',label:'Instagram Story',total:29},{key:'shared-unknown',label:'YouTube Post',total:1},{key:'track.lost',label:'Source inconnue',total:2},{key:'custom',label:'YouTube ou Instagram',total:3},{key:'tracked:renamed',label:'Publication 2024',total:4}],[{id:'renamed',name:'Publication 2024',historical:true,platform:''}]);
 assert.equal(result.find(row=>row.key==='unknown').total,32);assert.equal(result.find(row=>row.key==='other').total,7);assert(!result.some(row=>['youtube','instagram'].includes(row.key)));
});

test('legacy aliases and a tracked source remain separate contributions even when their labels match',()=>{
 const rows=[{key:'youtube',label:'YouTube Post',total:10},{key:'tracked:post',label:'YouTube Post',total:4},{key:'track.configured',label:'YouTube Description',total:6},{key:'youtube',label:'YouTube Post',total:2}],result=group(rows);
 assert.equal(result.length,1);assert.equal(result[0].total,22);assert.equal(result[0].sources.length,3);assert.equal(result[0].sources.find(row=>row.key==='youtube').total,12);
 assert.equal(result.reduce((n,p)=>n+p.total,0),rows.reduce((n,s)=>n+s.total,0));assert.equal(result[0].total,result[0].sources.reduce((n,s)=>n+s.total,0));
});

test('other platforms use strict readable aliases; near-matches and domains are not guessed',()=>{
 const rows=[{key:'a',label:'Facebook Post',total:1},{key:'b',label:'TikTok Bio',total:2},{key:'c',label:'Discord Message',total:3},{key:'d',label:'https://youtube.com',total:4},{key:'e',label:'Pas YouTube',total:5},{key:'f',label:'newsletter',total:6}];
 const result=group(rows);assert.equal(result.find(r=>r.key==='facebook').total,1);assert.equal(result.find(r=>r.key==='tiktok').total,2);assert.equal(result.find(r=>r.key==='discord').total,3);assert.equal(result.find(r=>r.key==='other').total,9);assert.equal(result.find(r=>r.key==='newsletter').total,6);
 assert.deepEqual(group([]),[]);
});
