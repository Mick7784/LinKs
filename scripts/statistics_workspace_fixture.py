"""Disposable HTTP fixture, used only by the browser acceptance test."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from fixtures import prepare, populate

os.environ['ANALYTICS_DB']=str(Path(sys.argv[1])/'stats.db')
os.environ['UPLOAD_DIR']=str(Path(sys.argv[1])/'uploads')
prepare(os.environ['ANALYTICS_DB'])
import analytics as a
a.init();populate(a)
today=datetime.now(a.PARIS).date()
with a.connection() as db:
    sources=a.tracked_links.source_rows(db)
    source=next(row for row in sources if row['platform']=='youtube')
    for index,(name,counts) in enumerate([('Lien multi-origines',{'youtube':10,'instagram':6,'discord':4}),('Même titre',{'youtube':5}),('Même titre',{'shared-unknown':3})]):
        item=a.tracked_links.create_link(db,{'name':name,'url':'https://example.org/'+str(index)},a.story_url_valid,a.now_iso())
        token=a.tracked_links.token_link(db,item['id'],source['id'],'https://links.example',a.now_iso())['token']
        for origin,count in counts.items():db.execute('INSERT INTO counts VALUES(?,?,?,?,?)',(str(today),origin,'tracked','tracked:'+token+':12',count))
    for n in range(30):
        day=str(today-timedelta(days=n))
        db.execute('INSERT INTO counts VALUES(?,?,?,?,?)',(day,'youtube','view','page',17+n%9))
    db.execute('INSERT INTO counts VALUES(?,?,?,?,?)',(str(today),'direct-inconnu','click','block:legacy-link-2',2))
    for n in range(3):
        ident=a.save_content(db,a.block_data({'type':'promo','internal_name':'Campagne de validation '+str(n+1),'title':'Offre de test','url':'https://example.org/campaign/'+str(n)}))
        token='st_'+str(n).zfill(16)
        db.execute('INSERT INTO story_links VALUES(?,?,?,?,0)',(token,ident,'Campagne test',a.now_iso()))
        db.execute('INSERT INTO counts VALUES(?,?,?,?,?)',(str(today),'youtube','story','story:'+token+':12',n+1))
server=a.serve(0,True,'127.0.0.1')
print('http://127.0.0.1:'+str(server.server_port),flush=True)
server.serve_forever()
