const {test}=require('node:test'),assert=require('node:assert/strict');
require('../admin/charts.js');
const series=[{key:'visits',index:1},{key:'clicks',index:2}];

test('missing measurements stay missing; measured zero remains a valid point',()=>{
 const days=[['2026-10-01',0,null],['2026-10-02',12],['2026-10-03',undefined,5]];
 const original=structuredClone(days),model=StudioCharts.plotModel(days,series);
 assert.deepEqual(model.values,[[0,null],[12,null],[null,5]]);
 assert.equal(model.peak,12);assert(model.max>=12);
 assert.deepEqual(days,original);
});
test('series visibility changes only the plot scale, never data or totals',()=>{
 const days=[['2026-10-01',150,4],['2026-10-02',0,9]],original=structuredClone(days);
 const model=StudioCharts.plotModel(days,series,new Set(['visits']));
 assert.equal(model.peak,9);assert.deepEqual(model.values,[[4],[9]]);
 const hidden=StudioCharts.plotModel(days,series,new Set(['visits','clicks']));
 assert.equal(hidden.peak,0);assert.equal(hidden.visible.length,0);
 assert.deepEqual(days,original);
});
test('long periods retain every daily measurement and source colours follow identity',()=>{
 const days=Array.from({length:400},(_,i)=>['day-'+i,i===399?123456789:0,1]);
 assert.equal(StudioCharts.plotModel(days,series).values.length,400);
 assert(StudioCharts.plotModel(days,series).max>=123456789);
 const original=StudioCharts.sourceColor('tracked:original');
 for(const key of ['other','tracked:renamed','unknown'])StudioCharts.sourceColor(key);
 assert.equal(StudioCharts.sourceColor('tracked:original'),original);
});
