const {test}=require('node:test'),assert=require('node:assert/strict');
require('../admin/partner-report.js');
const partners=[{id:'dom',name:'Domadoo'},{id:'reo',name:'Reolink'},{id:'san',name:'Sanyipace'}];

test('current explicit partner IDs aggregate filtered events, including archived links, never lifetime counters',()=>{
 const links=partners.map((p,i)=>({id:'link-'+i,name:p.name+' · Produit',partner_id:p.id,archived:i===0,clicks:999}));
 const rows=[{link_id:'link-0',total:2},{link_id:'link-0',total:3},{link_id:'link-1',total:4},{link_id:'link-2',total:1}],before=structuredClone({rows,links,partners});
 const report=StudioPartnerReport.attribute(rows,links,partners);
 assert.deepEqual(report.attributed.map(p=>[p.id,p.name,p.total]),[['dom','Domadoo',5],['reo','Reolink',4],['san','Sanyipace',1]]);
 assert.equal(report.attributed[0].links.length,1);assert.equal(report.attributed[0].links[0].total,5);
 assert.deepEqual(report.totals,{attributed:10,withoutPartner:0,unidentified:0});assert.deepEqual({rows,links,partners},before);
});

test('28 openings on identifiable links without a declared partner are legitimate even on configured partner domains',()=>{
 const links=[{id:'direct',name:'URL affiliée directe',url:'https://reolink.com/p?aff=1404',partner_id:''},{id:'none',name:'Sans partenaire',url:'https://domadoo.fr/p?domid=117',partner_id:''}];
 const report=StudioPartnerReport.attribute([{link_id:'direct',total:10},{link_id:'none',total:18}],links,partners);
 assert.equal(report.attributed.length,0);assert.equal(report.withoutPartner.length,2);assert.deepEqual(report.totals,{attributed:0,withoutPartner:28,unidentified:0});
});

test('missing link, missing association metadata and missing partner remain unidentified without domain inference',()=>{
 const links=[{id:'no-metadata',name:'Ancien',url:'https://domadoo.fr/p'},{id:'broken',name:'Référence absente',partner_id:'removed'},{id:'null',name:'Information absente',partner_id:null}];
 const report=StudioPartnerReport.attribute([{link_id:'lost',label:'Historique',total:2},{link_id:'no-metadata',total:3},{link_id:'broken',total:4},{link_id:'null',total:5}],links,partners);
 assert.deepEqual(report.totals,{attributed:0,withoutPartner:0,unidentified:14});assert.deepEqual(report.unidentified.map(row=>row.reason),['missing-link','missing-association','missing-partner','missing-association']);assert.equal(report.unidentified[0].id,null);
});

test('renames follow the partner ID; empty periods and sources never fall back to lifetime totals',()=>{
 const links=[{id:'link',name:'Lien',partner_id:'dom',clicks:900}];
 const report=StudioPartnerReport.attribute([{link_id:'link',total:1}],links,[{id:'dom',name:'Domadoo renommé'}]);
 assert.equal(report.attributed[0].name,'Domadoo renommé');assert.equal(report.totals.attributed,1);
 assert.deepEqual(StudioPartnerReport.attribute([],links,partners).totals,{attributed:0,withoutPartner:0,unidentified:0});
});
