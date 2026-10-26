'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
require('../admin/daily-report.js');
const name=key=>({youtube:'YouTube Post',instagram:'Instagram Bio'}[key]||'Source inconnue');

test('daily clicks/openings stay separate and duplicated campaign metrics are excluded',()=>{
 const report={rows:[{day:'2026-10-25',kind:'click',link:'block:a',label:'Public',source:'youtube',total:4},{day:'2026-10-25',kind:'click',link:'block:a',label:'Public',source:'instagram',total:2},{day:'2026-10-25',kind:'view',link:'',source:'youtube',total:900},{day:'2026-10-24',kind:'click',link:'block:a',source:'youtube',total:13}],
 tracked:[{day:'2026-10-25',link_id:'a',label:'Indépendant',source:'youtube',total:7}],
 stories:[{day:'2026-10-25',promotion_id:'a',label:'Campagne',source:'shared-unknown',total:3},{day:'2026-10-25',promotion_id:'a',label:'Campagne',source:'shared-unknown',total:5}],
 campaign_metrics:[{day:'2026-10-25',id:'a',kind:'click',total:4}],promo_code_copies:[{day:'2026-10-25',id:'a',total:30}]};
 const before=structuredClone(report),index=StudioDailyReport.index(report),day=StudioDailyReport.select(index,'2026-10-25','',name);
 assert.deepEqual(Object.values(day).map(group=>group.total),[6,7,8]);
 assert.equal(day.public.rows.length,1);assert.equal(day.campaigns.rows[0].sourceBreakdown[0].label,'Source inconnue');
 for(const group of Object.values(day))for(const row of group.rows)assert.equal(row.total,row.sourceBreakdown.reduce((sum,source)=>sum+source.total,0));
 assert.deepEqual(Object.values(StudioDailyReport.select(index,'2026-10-25','youtube',name)).map(group=>group.total),[4,7,0]);
 assert.deepEqual(Object.values(StudioDailyReport.select(index,'2026-10-24','',name)).map(group=>group.total),[13,0,0]);
 assert.deepEqual(Object.values(StudioDailyReport.select(index,'2026-10-23','',name)).map(group=>group.total),[0,0,0]);
 assert.deepEqual(report,before,'the original report and historical identities never change');
});

test('same titles, source names and campaign identities never merge distinct links or keys',()=>{
 const index=StudioDailyReport.index({rows:[{day:'d',kind:'click',link:'block:a',label:'Identique',source:'track.one',total:2},{day:'d',kind:'click',link:'block:a',label:'Identique',source:'track.two',total:3},{day:'d',kind:'click',link:'block:b',label:'Identique',source:'track.one',total:7}]});
 const day=StudioDailyReport.select(index,'d','',()=> 'Même libellé');
 assert.equal(day.public.rows.length,2);assert.equal(day.public.rows[0].sourceBreakdown.length,2);assert.deepEqual(day.public.rows.map(row=>row.total),[5,7]);
 assert.deepEqual(day.public.rows[0].sourceBreakdown.map(row=>row.key),['track.two','track.one']);
});

test('400-day histories remain indexed by recorded date and selection never uses lifetime totals',()=>{
 const report={tracked:Array.from({length:400},(_,i)=>({day:'day-'+i,link_id:'__proto__',label:'Lien',source:'known',source_name:'Source capturée',total:i+1,clicks:99999}))};
 const index=StudioDailyReport.index(report);assert.equal(index.size,400);
 assert.equal(StudioDailyReport.select(index,'day-399').tracked.total,400);
 assert.equal(StudioDailyReport.select(index,'day-0').tracked.rows[0].sourceBreakdown[0].label,'Source capturée');
 assert.equal(StudioDailyReport.select(index,'day-399','other').tracked.total,0);
});
