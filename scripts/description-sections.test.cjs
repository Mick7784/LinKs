const {test}=require('node:test'),assert=require('node:assert/strict');
const S=require('../admin/description-sections.js');
const definitions=[{id:'a',heading:'🍀 Titre A'},{id:'b',heading:'Titre B'}];
const a='🍀 Titre A\nTexte é 👩🏽‍💻',b='Titre B\nhttps://amzn.to/exact?tag=a%2Bb#x',text=a+'\n\n'+b;
const anchor=(id,quote,start)=>({id,quote,start,end:start+S.points(quote).length,status:'confirmed',candidates:[]});
const anchors=[anchor('a',a,0),anchor('b',b,S.points(a).length+2)];
test('UTF-16 selections and Python offsets roundtrip without splitting emoji',()=>{
 const value='A😀é👩🏽‍💻Z';
 for(let i=0;i<=S.points(value).length;i++)assert.equal(S.toPoint(value,S.toUTF16(value,i)),i);
 assert.equal(S.toPoint(value,2),1);assert.equal(S.toPoint(value,2,true),2);
 assert.equal(S.slice(value,1,2),'😀');assert.equal(S.slice(value,2,4),'é');
});
test('renaming a heading and editing URL content keep stable identities and shift following spans',()=>{
 const next=text.replace('🍀 Titre A','😀 Mon nouveau titre');const result=S.track(text,next,anchors,definitions);
 assert.equal(result[0].id,'a');assert.equal(result[0].status,'confirmed');
 assert.equal(result[0].quote,'😀 Mon nouveau titre\nTexte é 👩🏽‍💻');assert.equal(S.slice(next,result[1].start,result[1].end),b);
 assert.deepEqual(anchors[0],anchor('a',a,0));
});
test('moving whole sections preserves IDs and quotes',()=>{
 const moved=b+'\n\n'+a,result=S.track(text,moved,anchors,definitions);
 assert.deepEqual(result.map(s=>s.status),['confirmed','confirmed']);
 assert.equal(result[0].start,S.points(b).length+2);assert.equal(result[1].start,0);
});
test('cut and paste at a neighbouring section boundary restores the cut identity',()=>{
 const cut='\n\n'+b,intermediate=S.track(text,cut,anchors,definitions);
 assert.equal(intermediate[0].status,'ambiguous');assert.equal(intermediate[0].quote,a);
 const pasted=cut+a,result=S.track(cut,pasted,intermediate,definitions);
 assert.equal(result[0].status,'confirmed');assert.equal(result[0].start,S.points(cut).length);
 assert.equal(result[1].quote,b);
});
test('a complete replacement proposes headings but never confirms by guessing',()=>{
 const changed='🍀 Titre A\nNouveau contenu\n\nTitre B\nAutre contenu';
 const result=S.track(text,changed,anchors,definitions,{imported:true});
 assert.deepEqual(result.map(s=>s.status),['ambiguous','ambiguous']);assert.equal(result[0].candidates.length,1);
 assert.equal(S.slice(changed,result[1].candidates[0].start,result[1].candidates[0].end),'Titre B\nAutre contenu');
});
test('duplicate exact passages are ambiguous after importing',()=>{
 const result=S.track(text,text+'\n\n'+a,anchors,definitions,{imported:true});
 assert.equal(result[0].status,'ambiguous');assert.equal(result[0].candidates.length,2);assert.equal(result[1].status,'ambiguous');
});
test('manual association uses the explicit Unicode selection and rejects overlap',()=>{
 const result=S.track(text,'😀 Nouveau',anchors,definitions,{imported:true});
 const bound=S.bind('😀 Nouveau',result,'a',0,9);
 assert.equal(bound[0].quote,'😀 Nouveau');assert.equal(bound[0].id,'a');
 assert.throws(()=>S.bind('😀 Nouveau',bound,'b',1,9),/chevauche/);
 assert.throws(()=>S.bind('😀 Nouveau',bound,'a',0,20),/invalide/);
});
test('hidden default sections remain ambiguous until explicitly bound',()=>{
 const defs=[{id:'summary',heading:''},{id:'support',heading:'Soutien'},{id:'hashtags',heading:''}];
 const result=S.track('','Résumé 😀\n\nSoutien\nMerci\n\n#Zigbee #Domotique',defs.map(s=>({id:s.id,status:'ambiguous',start:null,end:null,quote:'',candidates:[]})),defs,{imported:true});
 assert(result.every(s=>s.status==='ambiguous'));assert(result.every(s=>s.candidates.length===1));
});
test('overlapping recovered passages require confirmation rather than stealing ownership',()=>{
 const previous=[anchor('a','abc',0),{id:'b',status:'ambiguous',start:null,end:null,quote:'b',candidates:[]}];
 const result=S.track('abc','abcd',previous,[{id:'a',heading:''},{id:'b',heading:''}]);
 assert(result.every(s=>s.status==='ambiguous'));
});
