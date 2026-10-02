const test=require('node:test'),assert=require('node:assert/strict');require('../admin/dates.js');
test('instance timezone roundtrip and daylight saving gap',()=>{
 assert.equal(LinksDates.local('2026-10-02T12:00:00Z','Europe/Paris'),'2026-10-02T14:00');
 assert.equal(LinksDates.instant('2026-10-02T14:00','Europe/Paris'),'2026-10-02T12:00:00.000Z');
 assert.equal(LinksDates.instant('2026-01-02T14:00','Europe/Paris'),'2026-01-02T13:00:00.000Z');
 assert.equal(LinksDates.instant('2026-10-02T08:00','America/New_York'),'2026-10-02T12:00:00.000Z');
 assert.throws(()=>LinksDates.instant('2026-03-29T02:30','Europe/Paris'),/n’existe pas/);
 assert.throws(()=>LinksDates.instant('invalid','UTC'),/invalide/);
});
