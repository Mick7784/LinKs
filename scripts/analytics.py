"""Aggregate-only analytics; no IP addresses, cookies or visitor identifiers."""
import base64, hmac, json, os, sqlite3, threading
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
if not (ROOT / 'links.json').exists(): ROOT = ROOT.parent
DB = os.environ.get('ANALYTICS_DB', '/data/analytics.db')
PASSWORD = os.environ.get('STATS_PASSWORD', '')
ORIGIN = os.environ.get('ANALYTICS_ORIGIN', 'https://links.domotik-studio.fr').rstrip('/')
ADMIN = ROOT / 'admin'
CONFIG = json.loads((ROOT / 'links.json').read_text())
CATALOG = {'latest-video': 'Dernière vidéo'}
for item in CONFIG['socials']:
    CATALOG['social:' + item['platform']] = 'Réseau · ' + item.get('label', item['platform'])
for item in CONFIG['links']:
    CATALOG['link:' + item['url']] = item['title']

def connection():
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    return db

def init():
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS counts(day TEXT, source TEXT, kind TEXT, link TEXT, total INTEGER NOT NULL, PRIMARY KEY(day,source,kind,link))')

def record(kind, source, link, day=None):
    day = day or datetime.now(ZoneInfo('Europe/Paris')).date().isoformat()
    with connection() as db:
        db.execute('INSERT INTO counts VALUES(?,?,?,?,1) ON CONFLICT(day,source,kind,link) DO UPDATE SET total=total+1', (day,source,kind,link))
        db.execute('DELETE FROM counts WHERE day < ?', ((date.fromisoformat(day)-timedelta(days=400)).isoformat(),))

def source_of(data):
    source = data.get('source', '')
    if not isinstance(source, str): raise ValueError()
    source = source.strip().lower()
    if source:
        return {'yt':'youtube','ig':'instagram','domotik-studio':'domotik-studio.fr'}.get(source, source) if source in ['yt','ig','youtube','instagram','facebook','tiktok','discord','google','newsletter','domotik-studio','domotik-studio.fr'] else 'autre-campagne'
    ref = data.get('referrer', '')
    if not isinstance(ref, str): raise ValueError()
    host = (urlsplit(ref).hostname or '').lower()
    if host == urlsplit(ORIGIN).hostname: return 'direct-inconnu'
    for domain, name in [('youtube.com','youtube'),('youtu.be','youtube'),('instagram.com','instagram'),('facebook.com','facebook'),('tiktok.com','tiktok'),('discord.com','discord'),('google.com','google'),('google.fr','google'),('domotik-studio.fr','domotik-studio.fr')]:
        if host == domain or host.endswith('.'+domain): return name
    return 'autre-site' if host else 'direct-inconnu'

def report(start, end, source=''):
    a,b = date.fromisoformat(start),date.fromisoformat(end)
    if a>b or (b-a).days>399: raise ValueError('Période maximale : 400 jours')
    where='day BETWEEN ? AND ?'; params=[start,end]
    if source: where+=' AND source=?'; params.append(source)
    with connection() as db:
        rows=[dict(r) for r in db.execute('SELECT * FROM counts WHERE '+where+' ORDER BY day', params)]
    return {'rows':rows, 'timezone':'Europe/Paris'}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def setup(self):
        super().setup(); self.connection.settimeout(10)
    def send(self, status, body=b'', mime='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers(); self.wfile.write(body)
    def authorized(self):
        expected='Basic '+base64.b64encode(('admin:'+PASSWORD).encode()).decode()
        return len(PASSWORD)>=16 and hmac.compare_digest(self.headers.get('Authorization','').encode(),expected.encode())
    def do_GET(self):
        if not self.server.admin: return self.send(404)
        if self.path == '/healthz':
            try:
                with connection() as db: db.execute('SELECT total FROM counts LIMIT 1').fetchone()
                return self.send(200, b'ok', 'text/plain')
            except sqlite3.Error: return self.send(503)
        if not self.authorized():
            self.send_response(401);self.send_header('WWW-Authenticate','Basic realm="Links stats", charset="UTF-8"');self.send_header('Cache-Control','no-store');self.end_headers();return
        url=urlsplit(self.path)
        if url.path=='/api/stats':
            try:
                p=parse_qs(url.query); today=datetime.now(ZoneInfo('Europe/Paris')).date()
                result=report(p.get('start',[(today-timedelta(days=29)).isoformat()])[0],p.get('end',[today.isoformat()])[0],p.get('source',[''])[0])
                return self.send(200,json.dumps(result).encode())
            except (ValueError, TypeError): return self.send(400,b'{"error":"Invalid period"}')
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','application/javascript'),'/style.css':('style.css','text/css')}
        if url.path not in files: return self.send(404)
        name,mime=files[url.path];self.send(200,(ADMIN/name).read_bytes(),mime)
    def do_POST(self):
        if self.server.admin or self.path!='/metrics': return self.send(404)
        if len(PASSWORD)<16: return self.send(503)
        if self.headers.get('Origin')!=ORIGIN: return self.send(403)
        if any(x in self.headers.get('User-Agent','').lower() for x in ['bot','spider','crawler','headless']): return self.send(204)
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=2048: return self.send(413)
            data=json.loads(self.rfile.read(n))
            if not isinstance(data,dict): raise ValueError()
            kind=data.get('kind'); key=data.get('link','')
            if kind not in ['view','click'] or not isinstance(key,str): raise ValueError()
            if kind=='click' and key not in CATALOG: raise ValueError()
            label=CATALOG[key] if kind=='click' else ''
            record(kind,source_of(data),label)
            self.send(204)
        except (ValueError,TypeError,KeyError): self.send(400)
        except sqlite3.Error: self.send(503)

def serve(port, admin, host):
    server=ThreadingHTTPServer((host,port),Handler);server.admin=admin
    return server

if __name__=='__main__':
    if len(PASSWORD)<16:
        raise SystemExit('STATS_PASSWORD must contain at least 16 characters')
    init()
    public=serve(3003,False,'127.0.0.1')
    threading.Thread(target=public.serve_forever,daemon=True).start()
    serve(8081,True,'0.0.0.0').serve_forever()
