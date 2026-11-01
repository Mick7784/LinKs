"""Private financial reporting. Amounts are signed integer cents, never floats.

Connectors supply a complete observation, not a ledger of invented daily gains.
Provider dates remain local wall dates when their timezone is not documented.
"""
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

PLATFORMS = [('domadoo', 'Portail Domadoo', 1), ('amazon', 'Amazon Partenaires', 0),
             ('affiliatly', 'Affiliatly', 0), ('goaffpro', 'GoAffPro', 0), ('awin', 'Awin', 0), ('impact', 'Impact', 0)]
TABLES = ('aff_platforms', 'aff_partners', 'aff_accounts', 'aff_snapshots', 'aff_transactions', 'aff_revisions', 'aff_vouchers', 'aff_runs')
SUMMARY_KEYS = {'clicks_30d','unique_clicks_30d','pending_sales_30d','approved_sales_30d','earnings_30d',
                'clicks_total','unique_clicks_total','approved_sales_total','earnings_total','payments_total','payments_pending','balance'}
LOCK = threading.Lock()

def stamp():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def migration_backup(path):
    path = Path(path)
    if not path.exists(): return
    with closing(sqlite3.connect(path)) as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='aff_accounts'").fetchone(): return
        target = path.with_name('pre-affiliation-v1.db')
        if not target.exists():
            with closing(sqlite3.connect(target)) as saved: db.backup(saved)

def initialize(db):
    # Additive, repeatable migration; existing links/campaigns are independent.
    statements = [
        'CREATE TABLE IF NOT EXISTS aff_platforms(id TEXT PRIMARY KEY,name TEXT NOT NULL,available INTEGER NOT NULL)',
        'CREATE TABLE IF NOT EXISTS aff_partners(id TEXT PRIMARY KEY,name TEXT NOT NULL)',
        '''CREATE TABLE IF NOT EXISTS aff_accounts(id TEXT PRIMARY KEY,partner_id TEXT NOT NULL REFERENCES aff_partners(id),
           platform_id TEXT NOT NULL REFERENCES aff_platforms(id),label TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,
           hour INTEGER NOT NULL DEFAULT 4,zone TEXT NOT NULL DEFAULT 'Europe/Paris',session_state TEXT NOT NULL DEFAULT 'disconnected',
           last_success TEXT,last_attempt TEXT,last_error TEXT,next_due TEXT,created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS aff_snapshots(id INTEGER PRIMARY KEY,account_id TEXT NOT NULL REFERENCES aff_accounts(id),
           observed_at TEXT NOT NULL,summary TEXT NOT NULL,row_count INTEGER NOT NULL,pages INTEGER NOT NULL,source TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS aff_transactions(account_id TEXT NOT NULL REFERENCES aff_accounts(id),provider_id TEXT NOT NULL,
           occurred_at TEXT NOT NULL,order_cents INTEGER NOT NULL,commission_cents INTEGER NOT NULL,currency TEXT NOT NULL,
           status TEXT NOT NULL,present INTEGER NOT NULL DEFAULT 1,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,
           PRIMARY KEY(account_id,provider_id))''',
        '''CREATE TABLE IF NOT EXISTS aff_revisions(id INTEGER PRIMARY KEY,account_id TEXT NOT NULL,provider_id TEXT NOT NULL,
           observed_at TEXT NOT NULL,before_json TEXT,after_json TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS aff_vouchers(account_id TEXT NOT NULL REFERENCES aff_accounts(id),position INTEGER NOT NULL,
           issued_on TEXT NOT NULL,amount_cents INTEGER NOT NULL,approved INTEGER NOT NULL,used INTEGER NOT NULL,
           PRIMARY KEY(account_id,position))''',
        '''CREATE TABLE IF NOT EXISTS aff_runs(id INTEGER PRIMARY KEY,account_id TEXT NOT NULL REFERENCES aff_accounts(id),
           started_at TEXT NOT NULL,finished_at TEXT,status TEXT NOT NULL,message TEXT,rows INTEGER,pages INTEGER)'''
    ]
    for sql in statements: db.execute(sql)
    db.executemany('INSERT OR IGNORE INTO aff_platforms VALUES(?,?,?)', PLATFORMS)
    db.execute("INSERT OR IGNORE INTO aff_partners VALUES('domadoo','Domadoo')")
    db.execute("INSERT OR IGNORE INTO aff_accounts(id,partner_id,platform_id,label,created_at) VALUES('domadoo','domadoo','domadoo','Compte Domadoo',?)", (stamp(),))
    db.execute("CREATE INDEX IF NOT EXISTS aff_date ON aff_transactions(account_id,occurred_at)")
    db.execute("CREATE INDEX IF NOT EXISTS aff_history ON aff_revisions(account_id,provider_id,id)")

def account(db, identity):
    row = db.execute('SELECT a.*,p.name partner FROM aff_accounts a JOIN aff_partners p ON p.id=a.partner_id WHERE a.id=?', (identity,)).fetchone()
    if row is None: raise ValueError('Compte introuvable.')
    return dict(row)

def money(value):
    if type(value) is not int or abs(value) > 10**14: raise ValueError('Montant invalide : relevé conservé.')
    return value

def validate(payload):
    if payload.get('complete') is not True or payload.get('currency') != 'EUR': raise ValueError('Relevé incomplet ou devise non reconnue.')
    summary = payload.get('summary', {})
    if set(summary) != SUMMARY_KEYS: raise ValueError('Structure du résumé Domadoo modifiée.')
    for value in summary.values(): money(value)
    rows = payload.get('transactions')
    if not isinstance(rows, list) or type(payload.get('pages')) is not int or payload['pages'] < 1: raise ValueError('Pagination invalide.')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'provider_id','occurred_at','order_cents','commission_cents','status','currency'}: raise ValueError('Vente invalide.')
        identity = row['provider_id']
        if not isinstance(identity,str) or not re.fullmatch(r'[0-9]{1,30}',identity) or identity in seen: raise ValueError('Identifiant manquant ou vente en double.')
        seen.add(identity)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',row['occurred_at']): raise ValueError('Date de vente invalide.')
        datetime.fromisoformat(row['occurred_at'])
        money(row['order_cents']); money(row['commission_cents'])
        if row['status'] not in {'approved','not_approved'} or row['currency'] != 'EUR': raise ValueError('Statut ou devise inconnu.')
    vouchers = payload.get('vouchers')
    if not isinstance(vouchers,list): raise ValueError('Bons de paiement incomplets.')
    for row in vouchers:
        if set(row) != {'issued_on','amount_cents','approved','used'}: raise ValueError('Bon de paiement invalide.')
        date.fromisoformat(row['issued_on']); money(row['amount_cents'])
        if type(row['approved']) is not bool or type(row['used']) is not bool: raise ValueError('Statut de bon inconnu.')
    return rows

def ingest(db, identity, payload, source='portal'):
    rows = validate(payload)
    account(db, identity)
    observed = stamp()
    old = {r['provider_id']:dict(r) for r in db.execute('SELECT * FROM aff_transactions WHERE account_id=?',(identity,))}
    fields = ('occurred_at','order_cents','commission_cents','currency','status','present')
    seen = set()
    for row in rows:
        key = row['provider_id']; seen.add(key)
        after = {**row,'present':1}
        previous = old.get(key)
        before = {k:previous[k] for k in fields} if previous else None
        current = {k:after[k] for k in fields}
        if before != current:
            db.execute('INSERT INTO aff_revisions(account_id,provider_id,observed_at,before_json,after_json) VALUES(?,?,?,?,?)',
                       (identity,key,observed,json.dumps(before) if before else None,json.dumps(current)))
        db.execute('''INSERT INTO aff_transactions VALUES(?,?,?,?,?,?,?,1,?,?) ON CONFLICT(account_id,provider_id) DO UPDATE SET
          occurred_at=excluded.occurred_at,order_cents=excluded.order_cents,commission_cents=excluded.commission_cents,
          currency=excluded.currency,status=excluded.status,present=1,last_seen=excluded.last_seen''',
          (identity,key,row['occurred_at'],row['order_cents'],row['commission_cents'],'EUR',row['status'],observed,observed))
    for key, previous in old.items():
        if key not in seen and previous['present']:
            before = {k:previous[k] for k in fields}; after = {**before,'present':0}
            db.execute('INSERT INTO aff_revisions(account_id,provider_id,observed_at,before_json,after_json) VALUES(?,?,?,?,?)',
                       (identity,key,observed,json.dumps(before),json.dumps(after)))
            db.execute('UPDATE aff_transactions SET present=0 WHERE account_id=? AND provider_id=?',(identity,key))
    db.execute('DELETE FROM aff_vouchers WHERE account_id=?',(identity,))
    for index,row in enumerate(payload['vouchers']):
        db.execute('INSERT INTO aff_vouchers VALUES(?,?,?,?,?,?)',(identity,index,row['issued_on'],row['amount_cents'],int(row['approved']),int(row['used'])))
    # Keep complete observations including voucher corrections, without redeemable codes.
    summary = {**payload['summary'],'vouchers':payload['vouchers']}
    db.execute('INSERT INTO aff_snapshots(account_id,observed_at,summary,row_count,pages,source) VALUES(?,?,?,?,?,?)',
               (identity,observed,json.dumps(summary),len(rows),payload['pages'],source))
    db.execute("UPDATE aff_accounts SET last_success=?,last_error=NULL,session_state=CASE WHEN ?='portal' THEN 'connected' ELSE session_state END WHERE id=?",(observed,source,identity))

def next_due(hour, zone, now=None):
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(zone))
    due = local.replace(hour=hour,minute=0,second=0,microsecond=0)
    if due <= local: due += timedelta(days=1)
    return due.astimezone(timezone.utc).isoformat().replace('+00:00','Z')

def configure(db, data):
    identity = data.get('id','domadoo'); current = account(db,identity)
    hour = data.get('hour',current['hour']); zone = data.get('zone',current['zone']); enabled = data.get('enabled',bool(current['enabled']))
    if type(hour) is not int or not 0<=hour<=23 or type(enabled) is not bool: raise ValueError('Horaire invalide.')
    try: ZoneInfo(zone)
    except (KeyError,TypeError,ValueError): raise ValueError('Fuseau horaire invalide.')
    if enabled and current['platform_id'] != 'domadoo': raise ValueError('Connecteur à venir.')
    db.execute('UPDATE aff_accounts SET enabled=?,hour=?,zone=?,next_due=? WHERE id=?',(int(enabled),hour,zone,next_due(hour,zone),identity))
    return {'ok':True}

def add_account(db, data):
    name = data.get('partner',''); label = data.get('label',''); platform = data.get('platform','')
    if not isinstance(name,str) or not 1<=len(name.strip())<=80 or not isinstance(label,str) or not 1<=len(label.strip())<=80: raise ValueError('Nom du partenaire et du compte requis (80 caractères maximum).')
    if platform not in {p[0] for p in PLATFORMS}: raise ValueError('Plateforme inconnue.')
    # Reuse a commercial partner, while each reporting account owns its history/session.
    row = db.execute('SELECT id FROM aff_partners WHERE lower(name)=lower(?)',(name.strip(),)).fetchone()
    partner = row[0] if row else uuid.uuid4().hex
    if not row: db.execute('INSERT INTO aff_partners VALUES(?,?)',(partner,name.strip()))
    identity = uuid.uuid4().hex
    db.execute('INSERT INTO aff_accounts(id,partner_id,platform_id,label,created_at) VALUES(?,?,?,?,?)',(identity,partner,platform,label.strip(),stamp()))
    return {'id':identity}

def period(query):
    start = query.get('start',''); end = query.get('end','')
    for value in (start,end):
        if value and (not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value) or not date.fromisoformat(value)): raise ValueError('Période invalide.')
    if start and end and start>end: raise ValueError('Période inversée.')
    return start,end

def loss_day(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ZoneInfo('Europe/Paris')).date().isoformat() if value else None


def transaction_source(db):
    # Derive the first disappearance from the existing immutable history: no migration
    # or synthetic dates for old backups. One row per account/provider ID, even after
    # repeated absences or reappearance. status and commission retain the last observation.
    db.create_function('aff_loss_day', 1, loss_day)
    return """(SELECT t.*, l.first_missing_at FROM aff_transactions t LEFT JOIN
      (SELECT account_id,provider_id,MIN(observed_at) first_missing_at FROM aff_revisions
       WHERE json_extract(after_json,'$.present')=0 GROUP BY account_id,provider_id) l
      ON l.account_id=t.account_id AND l.provider_id=t.provider_id)"""


def report(db, query):
    start,end = period(query); identity=query.get('account','')
    accounts=[dict(r) for r in db.execute('SELECT a.*,p.name partner,f.name platform,f.available FROM aff_accounts a JOIN aff_partners p ON p.id=a.partner_id JOIN aff_platforms f ON f.id=a.platform_id ORDER BY a.created_at,a.id')]
    for item in accounts:
        last=db.execute('SELECT * FROM aff_snapshots WHERE account_id=? ORDER BY id DESC LIMIT 1',(item['id'],)).fetchone()
        item['snapshot']={**dict(last),'summary':json.loads(last['summary'])} if last else None
        item['running']=bool(db.execute("SELECT 1 FROM aff_runs WHERE account_id=? AND status='running'",(item['id'],)).fetchone())
    selected=[a for a in accounts if not identity or a['id']==identity]
    if identity and not selected: raise ValueError('Compte introuvable.')
    clause='present=1'; args=[]
    if identity: clause+=' AND account_id=?'; args.append(identity)
    if start: clause+=' AND substr(occurred_at,1,10)>=?'; args.append(start)
    if end: clause+=' AND substr(occurred_at,1,10)<=?'; args.append(end)
    aggregate=[dict(r) for r in db.execute('SELECT account_id,status,SUM(commission_cents) cents,COUNT(*) sales FROM aff_transactions WHERE '+clause+' GROUP BY account_id,status',args)]
    daily=[dict(r) for r in db.execute('SELECT substr(occurred_at,1,10) day,status,SUM(commission_cents) cents FROM aff_transactions WHERE '+clause+' GROUP BY day,status ORDER BY day',args)]
    loss_clause='present=0'; loss_args=[]
    if identity: loss_clause+=' AND account_id=?'; loss_args.append(identity)
    if start: loss_clause+=' AND aff_loss_day(first_missing_at)>=?'; loss_args.append(start)
    if end: loss_clause+=' AND aff_loss_day(first_missing_at)<=?'; loss_args.append(end)
    losses=[dict(r) for r in db.execute('SELECT account_id,COUNT(*) sales,SUM(commission_cents) cents FROM '+transaction_source(db)+' WHERE '+loss_clause+' GROUP BY account_id',loss_args)]
    return {'losses':losses,'accounts':accounts,'platforms':[dict(r) for r in db.execute('SELECT * FROM aff_platforms')],
            'aggregate':aggregate,'daily':daily,'has_data':any(a['snapshot'] for a in selected),
            'coverage':{'ready':sum(bool(a['snapshot']) for a in selected),'total':len(selected)},'currency':'EUR'}

def transactions(db, query):
    identity=query.get('account','domadoo'); account(db,identity)
    start,end=period(query); clause='account_id=?'; args=[identity]
    source=transaction_source(db)
    period_day="CASE WHEN present=0 THEN aff_loss_day(first_missing_at) ELSE substr(occurred_at,1,10) END"
    if start: clause+=' AND '+period_day+'>=?'; args.append(start)
    if end: clause+=' AND '+period_day+'<=?'; args.append(end)
    status=query.get('status','')
    if status:
        if status not in {'approved','not_approved','missing','lost'}: raise ValueError('Statut invalide.')
        if status in {'missing','lost'}: clause+=' AND present=0'
        else: clause+=' AND present=1 AND status=?'; args.append(status)
    search=query.get('search','').strip().removeprefix('#')
    if len(search)>80: raise ValueError('Recherche trop longue.')
    if search: clause+=" AND instr(provider_id,?)>0"; args.append(search)
    page=max(1,int(query.get('page','1'))); size=20
    count=db.execute('SELECT COUNT(*) FROM '+source+' WHERE '+clause,args).fetchone()[0]
    page=min(page,max(1,(count+size-1)//size))
    items=[dict(r) for r in db.execute('SELECT * FROM '+source+' WHERE '+clause+' ORDER BY '+period_day+' DESC,occurred_at DESC,provider_id DESC LIMIT ? OFFSET ?',args+[size,(page-1)*size])]
    snapshot=db.execute('SELECT MAX(id) FROM aff_snapshots WHERE account_id=?',(identity,)).fetchone()[0]
    return {'items':items,'total':count,'page':page,'pages':max(1,(count+size-1)//size),'snapshot_id':snapshot}

def worker(action, data=None, timeout=40):
    token=os.environ.get('AFFILIATION_WORKER_TOKEN','')
    if not token: raise ValueError('Navigateur indisponible : utiliser l’image LinKs avec le service Affiliation.')
    request=Request('http://127.0.0.1:3004/'+action,json.dumps(data or {}).encode(),{'Content-Type':'application/json','Authorization':'Bearer '+token})
    try:
        with urlopen(request,timeout=timeout) as response: result=json.loads(response.read(32*1024*1024))
    except HTTPError as exc:
        try: result=json.loads(exc.read(2048))
        except ValueError: result={}
        raise ValueError(result.get('error','Navigateur indisponible.')) from None
    except (OSError,ValueError): raise ValueError('Navigateur indisponible ou délai dépassé. Dernier relevé conservé.') from None
    return result

def start_sync(connect, identity, identities=None):
    identities=identities or [identity]
    if not isinstance(identities,list) or not identities or len(identities)>100 or len(set(identities))!=len(identities): raise ValueError('Sélection de comptes invalide.')
    with connect() as db:
        for selected in identities:
            a=account(db,selected)
            if a['platform_id']!='domadoo': raise ValueError('Connecteur à venir.')
    if not LOCK.acquire(blocking=False): raise ValueError('Une synchronisation est déjà en cours.')
    try:
        with connect() as db:
            started=stamp()
            runs=[]
            for selected in identities:
                run=db.execute("INSERT INTO aff_runs(account_id,started_at,status) VALUES(?,?,'running')",(selected,started)).lastrowid
                runs.append((selected,run))
                db.execute('UPDATE aff_accounts SET last_attempt=? WHERE id=?',(started,selected))
        def collect():
            try:
                for selected,run_id in runs:
                    try:
                        payload=worker('collect',{'account':selected},timeout=2000)
                        with connect() as db:
                            ingest(db,selected,payload)
                            db.execute("UPDATE aff_runs SET status='success',finished_at=?,rows=?,pages=? WHERE id=?",(stamp(),len(payload['transactions']),payload['pages'],run_id))
                    except Exception as exc:
                        message=str(exc) if isinstance(exc,ValueError) else 'Collecte interrompue. Dernier relevé conservé.'
                        with connect() as db:
                            db.execute("UPDATE aff_runs SET status='failed',finished_at=?,message=? WHERE id=?",(stamp(),message,run_id))
                            db.execute("UPDATE aff_accounts SET last_error=?,session_state=CASE WHEN ? LIKE '%Reconnexion requise%' THEN 'reconnect' ELSE session_state END WHERE id=?",(message,message,selected))
            finally: LOCK.release()
        threading.Thread(target=collect,daemon=True).start()
    except Exception:
        LOCK.release(); raise
    return {'ok':True,'run':run}

def recover(db):
    db.execute("UPDATE aff_accounts SET last_error='Collecte interrompue par le redémarrage. Dernier relevé conservé.' WHERE id IN (SELECT account_id FROM aff_runs WHERE status='running')")
    db.execute("UPDATE aff_runs SET status='failed',finished_at=?,message='Service redémarré.' WHERE status='running'",(stamp(),))

def export_backup(db):
    """Financial observations only; encrypted browser sessions/key are excluded."""
    return {'version':1,'tables':{table:[dict(row) for row in db.execute('SELECT * FROM '+table)] for table in TABLES}}

def restore_backup(db, bundle):
    if bundle is None: return 'absent'
    if not isinstance(bundle,dict) or bundle.get('version')!=1 or set(bundle.get('tables',{}))!=set(TABLES):
        raise ValueError('Sauvegarde Affiliation invalide.')
    tables=bundle['tables']
    # Validate SQL shape and referential integrity in a disposable database first.
    checked=sqlite3.connect(':memory:');checked.row_factory=sqlite3.Row
    try:
        checked.execute('PRAGMA foreign_keys=ON');initialize(checked)
        for table in reversed(TABLES): checked.execute('DELETE FROM '+table)
        for table in TABLES:
            columns=[row[1] for row in checked.execute('PRAGMA table_info('+table+')')]
            if not isinstance(tables[table],list): raise ValueError('Table Affiliation invalide.')
            for row in tables[table]:
                if not isinstance(row,dict) or set(row)!=set(columns) or any(not isinstance(v,(str,int,type(None))) for v in row.values()): raise ValueError('Ligne Affiliation invalide.')
                checked.execute('INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',[row[c] for c in columns])
        if {tuple(r) for r in checked.execute('SELECT id,name,available FROM aff_platforms')}!=set(PLATFORMS): raise ValueError('Plateformes de sauvegarde incompatibles.')
        for row in checked.execute('SELECT * FROM aff_accounts'):
            if not re.fullmatch(r'(domadoo|[a-f0-9]{32})',row['id']) or len(row['label'])>80: raise ValueError('Compte sauvegardé invalide.')
            configure(checked,{'id':row['id'],'enabled':False,'hour':row['hour'],'zone':row['zone']})
        for row in checked.execute('SELECT * FROM aff_transactions'):
            money(row['commission_cents']);money(row['order_cents']);datetime.fromisoformat(row['occurred_at'])
            if row['status'] not in {'approved','not_approved'} or row['currency']!='EUR' or row['present'] not in (0,1): raise ValueError('Vente sauvegardée invalide.')
        for row in checked.execute('SELECT summary FROM aff_snapshots'):
            summary=json.loads(row['summary'])
            validate({'complete':True,'currency':'EUR','summary':{k:v for k,v in summary.items() if k!='vouchers'},'pages':1,'transactions':[],'vouchers':summary.get('vouchers',[])})
        if list(checked.execute('PRAGMA foreign_key_check')): raise ValueError('Référence Affiliation manquante.')
    except (sqlite3.Error,TypeError,KeyError,ValueError) as exc:
        raise ValueError('Sauvegarde Affiliation invalide ou incompatible.') from exc
    finally: checked.close()
    initialize(db)
    # Never roll current financial history back when restoring a content backup.
    if db.execute('SELECT 1 FROM aff_snapshots LIMIT 1').fetchone() or db.execute("SELECT 1 FROM aff_accounts WHERE id!='domadoo' LIMIT 1").fetchone(): return 'conservé'
    for table in reversed(TABLES): db.execute('DELETE FROM '+table)
    for table in TABLES:
        for row in tables[table]:
            values=dict(row)
            if table=='aff_accounts': values.update(enabled=0,session_state='disconnected',next_due=None)
            if table=='aff_runs' and values['status']=='running': values.update(status='failed',finished_at=stamp(),message='Sauvegarde restaurée.')
            db.execute('INSERT INTO '+table+' ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')',list(values.values()))
    return 'restauré ; reconnexion requise'

def scheduler(connect):
    with connect() as db: recover(db)
    while True:
        try:
            with connect() as db:
                due=db.execute("SELECT id,hour,zone FROM aff_accounts WHERE enabled=1 AND platform_id='domadoo' AND (next_due IS NULL OR next_due<=?) ORDER BY next_due LIMIT 1",(stamp(),)).fetchone()
                if due and not LOCK.locked():
                    db.execute('UPDATE aff_accounts SET next_due=? WHERE id=?',(next_due(due['hour'],due['zone']),due['id']))
                else: due=None
            if due: start_sync(connect,due['id'])
        except (ValueError,OSError,sqlite3.Error): pass
        time.sleep(30)

def get(connect, action, query):
    with connect() as db:
        if action=='overview': return report(db,query)
        if action=='transactions': return transactions(db,query)
        identity=query.get('account','domadoo'); account(db,identity)
        if action=='history':
            return {'items':[dict(r) for r in db.execute('SELECT * FROM aff_revisions WHERE account_id=? AND provider_id=? ORDER BY id DESC',(identity,query.get('id','')))]}
        if action=='payments': return {'items':[dict(r) for r in db.execute('SELECT * FROM aff_vouchers WHERE account_id=? ORDER BY position',(identity,))]}
        if action=='runs': return {'items':[dict(r) for r in db.execute('SELECT * FROM aff_runs WHERE account_id=? ORDER BY id DESC LIMIT 30',(identity,))]}
    raise ValueError('Action inconnue.')

def post(connect, action, data):
    identity=data.get('account',data.get('id','domadoo'))
    if action=='sync': return start_sync(connect,identity,data.get('accounts'))
    with connect() as db:
        if action=='accounts': return add_account(db,data)
        if action=='settings': return configure(db,data)
        a=account(db,identity)
    if a['platform_id']!='domadoo': raise ValueError('Connecteur à venir.')
    if action in {'login/start','login/state','login/input','login/close','login/verify','disconnect'}:
        result=worker(action,{**data,'account':identity},timeout=60 if action=='login/start' else 40)
        if result.get('connected') or action=='disconnect':
            with connect() as db:
                db.execute('UPDATE aff_accounts SET session_state=? WHERE id=?',('connected' if result.get('connected') else 'disconnected',identity))
                if action=='disconnect': db.execute('UPDATE aff_accounts SET enabled=0 WHERE id=?',(identity,))
        return result
    raise ValueError('Action inconnue.')
