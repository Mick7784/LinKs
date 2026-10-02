"""Generic disposable fixtures. Never imported by application startup."""
import json, sqlite3, sys
from pathlib import Path

def prepare(database,origin='https://links.example'):
    Path(database).parent.mkdir(parents=True,exist_ok=True)
    values={'app.config_schema_version':'1','app.setup_completed':'true','auth.mode':'external',
      'profile.name':'Test Creator','profile.tagline':'Une page de test','profile.description':'Liens de test',
      'profile.logo':'/assets/link-shopping.webp','profile.avatar':'/assets/link-shopping.webp','footer.owner':'Test Creator',
      'app.timezone':'Europe/Paris','site.url':origin,'analytics.enabled':'true','video.enabled':'true',
      'analytics.source_rules':'[]','analytics.metric_aliases':json.dumps({'Amazon':'block:legacy-link-2','Domadoo':'block:legacy-link-3','Réseau · Me contacter par e-mail':'button:legacy-button-2'})}
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        db.executemany('INSERT OR REPLACE INTO settings VALUES(?,?)',values.items())

def populate(a):
    links=[('Communauté','https://discord.gg/test','discord'),('Instagram','https://instagram.com/example','instagram'),('Amazon','https://amzn.to/example','cart'),('Domadoo','https://partner.example/shop','home'),('Contact','mailto:contact@example.com','mail')]
    with a.connection() as db:
        for i,(name,url,icon) in enumerate(links):
            key=a.save_content(db,a.block_data({'type':'classic','internal_name':name,'title':name,'url':url,'icon':icon}))
            db.execute('UPDATE content_blocks SET id=? WHERE id=?',('legacy-link-'+str(i),key))
        for i,(label,icon,url) in enumerate([('YouTube','youtube','https://youtube.com/@example'),('Instagram','instagram','https://instagram.com/example'),('Me contacter par e-mail','email','mailto:contact@example.com')]):
            db.execute('INSERT INTO top_buttons VALUES(?,?,?,?,?,1,?,?)',('legacy-button-'+str(i),icon,label,url,i,a.now_iso(),a.now_iso()))

if __name__=='__main__':
    import os
    database=sys.argv[1];prepare(database,sys.argv[2] if len(sys.argv)>2 else 'https://links.example')
    os.environ['ANALYTICS_DB']=database
    import analytics
    analytics.init();populate(analytics)
