"""Campaign selection contracts against disposable SQLite and real HTTP routes."""
import copy
import json
import os
import tempfile
import threading
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import analytics as a
from fixtures import prepare

AT='2099-01-02T12:00:00Z'
PERIOD={'start_at':'2099-01-01T00:00:00Z','end_at':'2099-01-04T00:00:00Z'}


class CampaignSelectionTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        root=Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        prepare(root/'stats.db')
        for name,value in [('DB',str(root/'stats.db')),('DATA_DIR',root),('UPLOADS',root/'uploads'),
                           ('ORIGIN','https://links.example'),('PARIS',a.PARIS)]:
            self.stack.enter_context(patch.object(a,name,value))
        a.init()

    def create(self,name='Campaign',**extra):
        data={'type':'promo','internal_name':name,'title':name,'url':'https://partner.example/offer',**extra}
        with a.connection() as db:return a.save_content(db,a.block_data(data))

    def server(self,admin=True):
        server=a.serve(0,admin,'127.0.0.1')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),thread.join()))
        return 'http://127.0.0.1:'+str(server.server_port)

    def request(self,url,data=None,method=None):
        try:
            response=urlopen(Request(url,json.dumps(data).encode() if data is not None else None,
                            {'X-Links-Request':'1','Content-Type':'application/json'},method=method))
        except HTTPError as exc:response=exc
        with response:
            body=response.read()
            return response.code,json.loads(body) if body else None

    def config_at(self,at=AT,snapshot=False):
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return datetime.fromisoformat(at.replace('Z','+00:00')).astimezone(tz)
        with patch.object(a,'datetime',Clock):return a.public_config(snapshot=snapshot)

    def test_four_one_offs_wait_then_take_the_free_slot_at_exact_end(self):
        ids=[self.create(str(i),**({**PERIOD,'end_at':'2099-01-03T00:00:00Z'} if i==0 else PERIOD)) for i in range(4)]
        selection=a.campaign_selection(AT)
        self.assertEqual(selection['eligible_ids'],ids)
        self.assertEqual(selection['visible_ids'],ids[:3])
        self.assertEqual(selection['waiting_ids'],ids[3:])
        self.assertEqual(selection['items'][3]['selection_state'],'waiting')
        self.assertTrue(selection['items'][3]['eligible'])
        end=a.campaign_selection('2099-01-03T00:00:00Z')
        self.assertEqual(end['visible_ids'],ids[1:])
        self.assertEqual(end['items'][0]['selection_state'],'ended')
        self.assertEqual(end['waiting_ids'],[])
        config=self.config_at()
        self.assertEqual(config['visible_campaign_ids'],ids[:3])
        self.assertEqual([r['id'] for r in config['links']],ids)  # PulSe sees all four.
        self.assertEqual(config['next_campaign_change'],'2099-01-03T00:00:00Z')

    def test_duration_overrides_legacy_high_priority_and_visual_type(self):
        permanent=[self.create('Permanent '+str(i),type='featured',priority='high') for i in range(3)]
        punctual=[self.create('One off '+str(i),**PERIOD) for i in range(2)]
        selection=a.campaign_selection(AT)
        self.assertEqual(selection['visible_ids'],punctual+permanent[:1])
        self.assertEqual(selection['waiting_ids'],permanent[1:])
        self.assertEqual(a.campaign_selection('2099-01-04T00:00:00Z')['visible_ids'],permanent)
        self.assertEqual([r['id'] for r in self.config_at()['links']],punctual+permanent)

    def test_default_creation_order_and_manual_order_survive_restart(self):
        old=self.create('Old',**PERIOD)
        new=self.create('New',priority='high',**PERIOD)
        permanent=self.create('Permanent')
        self.assertEqual(a.campaign_selection(AT)['eligible_ids'],[old,new,permanent])
        admin=self.server()
        self.assertEqual(self.request(admin+'/api/content/reorder',{'ids':[permanent,new,old]})[0],204)
        a.init()
        self.assertEqual(a.campaign_selection(AT)['eligible_ids'],[new,old,permanent])

    def test_created_at_then_id_break_equal_position_ties_deterministically(self):
        ids=[self.create(str(i),**PERIOD) for i in range(4)]
        with a.connection() as db:
            db.execute("UPDATE content_blocks SET position=0,created_at='2026-01-01T00:00:00Z'")
            db.execute("UPDATE content_blocks SET created_at='2025-12-31T23:00:00Z' WHERE id=?",(ids[-1],))
            rows=list(db.execute('SELECT * FROM content_blocks'))
        expected=[ids[-1]]+sorted(ids[:-1])
        for order in (rows,list(reversed(rows)),rows[1:]+rows[:1]):
            self.assertEqual(a.select_campaigns(order,AT)['eligible_ids'],expected)

    def test_non_participants_have_distinct_states_and_cannot_consume_slots(self):
        expected={}
        for state,extra in [('draft',{'draft':True}),('disabled',{'active':False}),
                            ('scheduled',{'start_at':'2099-02-01T00:00:00Z','end_at':None}),
                            ('ended',{'end_at':'2099-01-02T12:00:00Z'})]:
            expected[self.create(state,**{**PERIOD,**extra})]=state
        for state,field in [('archived','archived'),('retired','retired')]:
            ident=self.create(state,**PERIOD);expected[ident]=state
            with a.connection() as db:db.execute('UPDATE content_blocks SET '+field+'=1 WHERE id=?',(ident,))
        self.create('Classic',type='classic')
        visible=self.create('Visible',**PERIOD);expected[visible]='visible'
        result=a.campaign_selection(AT)
        self.assertEqual({r['id']:r['selection_state'] for r in result['items']},expected)
        self.assertEqual(result['eligible_ids'],[visible])
        self.assertEqual(result['waiting_ids'],[])

    def test_future_preview_is_private_read_only_and_does_not_change_live_selection(self):
        future=self.create('Future',**PERIOD)
        admin=self.server();public=self.server(False)
        before=json.loads(a.export_backup())['tables']
        status,result=self.request(admin+'/api/promotions/selection?'+urlencode({'at':AT}))
        self.assertEqual(status,200)
        self.assertEqual(result['visible_ids'],[future])
        self.assertEqual(json.loads(a.export_backup())['tables'],before)
        self.assertEqual(a.public_config()['visible_campaign_ids'],[])
        self.assertEqual(self.request(public+'/api/promotions/selection?'+urlencode({'at':AT}))[0],404)
        self.assertNotIn(future,json.dumps(a.public_config()))
        for query in ['at=','at=bad','at='+AT+'&at='+AT]:
            self.assertEqual(self.request(admin+'/api/promotions/selection?'+query)[0],400)

    def test_many_scheduled_campaigns_can_be_created_edited_restored_and_duplicated(self):
        admin=self.server();ids=[]
        data={'type':'promo','internal_name':'Unlimited','title':'Unlimited','url':'https://partner.example',**PERIOD}
        for _ in range(12):
            status,result=self.request(admin+'/api/content',data)
            self.assertEqual(status,201);ids.append(result['id'])
        check=self.request(admin+'/api/promotions/check',data)[1]
        self.assertTrue(check['allowed']);self.assertEqual(check['maximum'],13)
        self.assertEqual(self.request(admin+'/api/content/'+ids[0],data,'PUT')[0],204)
        self.assertEqual(self.request(admin+'/api/content/'+ids[0]+'/archive',{})[0],204)
        self.assertEqual(self.request(admin+'/api/content/'+ids[0]+'/restore',{})[0],204)
        status,duplicate=self.request(admin+'/api/content/'+ids[0]+'/duplicate',{})
        self.assertEqual(status,201)
        self.assertNotIn(duplicate['id'],a.campaign_selection(AT)['eligible_ids'])
        self.assertEqual(a.campaign_selection(AT)['waiting_ids'],ids[3:])

    def test_timezone_offsets_dst_and_half_open_intervals(self):
        early=self.create('Before fall-back',start_at='2026-10-25T02:00:00+02:00',end_at='2026-10-25T02:00:00+01:00')
        late=self.create('After fall-back',start_at='2026-10-25T02:00:00+01:00',end_at='2026-10-25T03:00:00+01:00')
        self.assertEqual(a.campaign_selection('2026-10-25T00:00:00Z')['eligible_ids'],[early])
        self.assertEqual(a.campaign_selection('2026-10-25T01:00:00Z')['eligible_ids'],[late])
        self.assertEqual(a.campaign_selection('2026-10-25T02:00:00Z')['eligible_ids'],[])
        spring=self.create('Spring',start_at='2026-03-29T01:30:00+01:00',end_at='2026-03-29T03:30:00+02:00')
        self.assertEqual(a.campaign_selection('2026-03-29T03:00:00+02:00')['eligible_ids'],[spring])
        self.assertEqual(a.instant('2026-10-28T12:00:00',strict=True).hour,11)
        for invalid in ['2026-03-29T02:30:00','2026-10-25T02:30:00']:
            with self.assertRaises(ValueError):self.create('Invalid',start_at=invalid)
            with self.assertRaises(ValueError):a.campaign_selection(invalid)
        with self.assertRaises(ValueError):self.create('Invalid',start_at=PERIOD['end_at'],end_at=PERIOD['start_at'])
        with self.assertRaises(ValueError):a.campaign_selection(datetime(2099,1,2))

    def test_historical_featured_open_intervals_backup_and_identifiers_are_preserved(self):
        ids=[self.create(str(i),type='featured' if i%2 else 'promo',**PERIOD) for i in range(4)]
        start_only=self.create('Legacy start only',type='featured',start_at=PERIOD['start_at'])
        end_only=self.create('Legacy end only',type='featured',end_at=PERIOD['end_at'])
        alias=a.story_link(ids[-1],'instagram')
        a.record('click','youtube','block:'+ids[0],'2026-10-28')
        before=json.loads(a.export_backup());selection=a.campaign_selection(AT)
        for _ in range(2):a.init()
        for table in ['content_blocks','story_links','short_aliases','counts']:
            self.assertEqual(json.loads(a.export_backup())['tables'][table],before['tables'][table])
        a.restore_backup(copy.deepcopy(before))
        self.assertEqual(a.campaign_selection(AT),selection)
        self.assertEqual(a.story_link(ids[-1],'instagram'),alias)
        self.assertEqual(next(r for r in a.content_list() if r['id']==ids[0])['clicks'],1)
        states={r['id']:r for r in selection['items']}
        self.assertEqual(states[start_only]['duration_type'],'permanent')
        self.assertEqual(states[end_only]['duration_type'],'one_off')
        self.assertEqual(len(selection['eligible_ids']),6)

    def test_static_fallback_ranks_future_campaigns_and_excludes_private_content(self):
        permanent=self.create('Permanent',priority='high')
        future=[self.create('Future '+str(i),**PERIOD) for i in range(4)]
        draft=self.create('Private',draft=True)
        disabled=self.create('Disabled',active=False)
        snapshot=self.config_at(snapshot=True)
        self.assertNotIn('visible_campaign_ids',snapshot)  # Cannot freeze a future selection.
        self.assertEqual([r['id'] for r in snapshot['links']],future+[permanent])
        self.assertNotIn(draft,json.dumps(snapshot));self.assertNotIn(disabled,json.dumps(snapshot))
        self.assertEqual(a.public_config()['visible_campaign_ids'],[permanent])

    def test_waiting_campaign_is_still_shareable_by_pulse(self):
        ids=[self.create(str(i),end_at='2099-12-31T00:00:00Z') for i in range(4)]
        self.assertEqual(a.campaign_selection()['waiting_ids'],ids[3:])
        with patch.dict(os.environ,{'PULSE_BRIDGE_TOKEN':'x'*64}):
            url=self.server()+'/api/pulse/story-link'
            with urlopen(Request(url,json.dumps({'type':'campaign','id':ids[-1]}).encode(),
                         {'Authorization':'Bearer '+'x'*64,'Content-Type':'application/json'})) as response:
                self.assertEqual(response.code,200);shared=json.load(response)
        self.assertEqual(shared['url'],a.pulse_story_link({'type':'campaign','id':ids[-1]})['url'])
        with a.connection() as db:db.execute('UPDATE content_blocks SET active=0 WHERE id=?',(ids[0],))
        self.assertEqual(a.campaign_selection()['visible_ids'],ids[1:])
        self.assertEqual(shared['url'],a.pulse_story_link({'type':'campaign','id':ids[-1]})['url'])


if __name__=='__main__':unittest.main()
