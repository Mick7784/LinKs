"""Read-only overview: current approved EUR commissions, attributed to sale dates.

No approval-date ledger is inferred. Amazon has no equivalent approval status and
is deliberately excluded, regardless of its number of overlapping report views.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PARIS = ZoneInfo('Europe/Paris')
MAX_DAYS = 3660


def calendar_days(start, end):
    return [start + timedelta(days=i) for i in range((end-start).days+1)]


def previous_year(day):
    try:
        return day.replace(year=day.year-1)
    except ValueError:
        return None  # February 29 has no invented February 28 equivalent.


def local_day(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(PARIS).date()


def build(db, accounts, start='', end='', now=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(PARIS).date()
    sources = []
    for account in accounts:
        source = {'id': account['id'], 'partner_id': account['partner_id'],
                  'name': account['partner'], 'label': account['label'],
                  'eligible': account['platform_id'] == 'domadoo',
                  'collected_at': None, 'first_day': None, 'amounts': {}, 'foreign_days': set()}
        if not source['eligible']:
            source['reason'] = ('Statut des commissions Amazon non comparable au statut approuvé ; rapports conservés dans la vue Amazon.'
                                if account['platform_id'] == 'amazon' else 'Aucun contrat de commission comparable pour cette plateforme.')
        else:
            snapshot = db.execute('SELECT observed_at FROM aff_snapshots WHERE account_id=? ORDER BY id DESC LIMIT 1', (source['id'],)).fetchone()
            source['collected_at'] = snapshot['observed_at'] if snapshot else None
            rows = list(db.execute('SELECT substr(occurred_at,1,10) day,present,status,currency,commission_cents FROM aff_transactions WHERE account_id=?', (source['id'],)))
            # Earliest known sale is a conservative lower bound. Empty histories
            # and dates before it cannot establish an explicit zero.
            source['first_day'] = min((r['day'] for r in rows), default=None)
            for row in rows:
                if not row['present']:
                    continue
                if row['currency'] != 'EUR':
                    source['foreign_days'].add(row['day'])
                elif row['status'] == 'approved':
                    source['amounts'][row['day']] = source['amounts'].get(row['day'], 0) + row['commission_cents']
            source['reason'] = '' if snapshot else 'Aucun relevé complet collecté.'
        sources.append(source)

    finish = date.fromisoformat(end) if end else max(today, date.fromisoformat(start)) if start else today
    known = [s['first_day'] for s in sources if s['first_day']]
    known = [day for day in known if day <= finish.isoformat()]
    begin = date.fromisoformat(start) if start else date.fromisoformat(min(known)) if known else finish-timedelta(days=29)
    if begin > finish:
        raise ValueError('Période inversée.')
    if (finish-begin).days >= MAX_DAYS:
        raise ValueError('Choisissez une période de 3 660 jours maximum pour la vue journalière.')
    days = calendar_days(begin, finish)
    eligible = [s for s in sources if s['eligible']]

    def point(source, day):
        if day is None:
            return {'cents': None, 'status': 'unavailable', 'reason': 'Pas de date calendaire équivalente.'}
        key = day.isoformat()
        amount = source['amounts'].get(key)
        observed = local_day(source['collected_at']) if source['collected_at'] else None
        if not observed or not source['first_day'] or key < source['first_day'] or day > observed or day > today:
            return {'cents': None, 'status': 'unavailable', 'reason': 'Journée hors de la couverture connue du relevé.'}
        if day == today or day == observed or key in source['foreign_days']:
            return {'cents': amount, 'status': 'partial', 'reason': 'Journée provisoire, collecte en cours de journée ou devise exclue.'}
        return {'cents': amount if amount is not None else 0, 'status': 'complete', 'reason': ''}

    def aggregate(day):
        parts = []
        for source in eligible:
            parts.append({'account_id': source['id'], 'partner_id': source['partner_id'], **point(source, day)})
        values = [p['cents'] for p in parts if p['cents'] is not None]
        complete = bool(parts) and all(p['status'] == 'complete' for p in parts)
        return {'day': day.isoformat() if day else None, 'cents': sum(values) if values else None,
                'status': 'complete' if complete else 'partial' if values else 'unavailable',
                'provisional': day == today, 'parts': parts}

    daily = [aggregate(day) for day in days]
    values = [p['cents'] for p in daily if p['cents'] is not None]
    total = sum(values) if values else None
    partners = []
    for partner_id in dict.fromkeys(s['partner_id'] for s in sources):
        group = [s for s in sources if s['partner_id'] == partner_id]
        parts = [p for item in daily for p in item['parts'] if p['partner_id'] == partner_id]
        amounts = [p['cents'] for p in parts if p['cents'] is not None]
        partners.append({'id': partner_id, 'name': group[0]['name'], 'cents': sum(amounts) if amounts else None,
                         'status': 'complete' if parts and all(p['status'] == 'complete' for p in parts) and all(s['eligible'] for s in group) else 'partial' if amounts else 'unavailable'})

    def comparison(reference_days):
        series = [aggregate(day) for day in reference_days]
        paired = [r['cents'] if c['status'] == r['status'] == 'complete' else None for c, r in zip(daily, series)]
        continuous = all(reference_days) and (reference_days[-1]-reference_days[0]).days+1 == len(days)
        valid = bool(eligible) and continuous and all(v is not None for v in paired) and all(d['status'] == 'complete' for d in daily)
        base = sum(paired) if valid else None
        reason = ''
        if not continuous:
            reason = 'Fenêtre N-1 non équivalente autour du 29 février.'
        elif not valid:
            reason = 'Couverture incomplète, journée provisoire ou partenaire sans historique comparable.'
        elif base <= 0:
            reason = 'Base de comparaison nulle ou négative.'
        return {'daily': [{'day': r['day'], 'cents': value} for r, value in zip(series, paired)],
                'percent': (total-base)*100/base if valid and base > 0 else None, 'reason': reason,
                'start': series[0]['day'], 'end': series[-1]['day'],
                'partial': any(v is None for v in paired), 'available': any(v is not None for v in paired)}

    coverage = []
    for source in sources:
        points = [point(source, day) for day in days] if source['eligible'] else []
        statuses = [p['status'] for p in points]
        status = 'complete' if statuses and all(s == 'complete' for s in statuses) else 'partial' if any(p['cents'] is not None for p in points) else 'unavailable'
        reason = source['reason'] or ('' if status == 'complete' else 'Couverture journalière incomplète ; les absences ne valent pas zéro.')
        collected = source['collected_at']
        stale = bool(collected and (now-datetime.fromisoformat(collected.replace('Z', '+00:00'))).total_seconds() > 36*3600)
        coverage.append({k: source[k] for k in ('id','partner_id','name','label','eligible','collected_at')} | {'status': status, 'reason': reason, 'stale': stale})
    return {'metric': 'approved_commissions_by_sale_day', 'label': 'Commissions approuvées consolidées',
            'description': 'Statut actuel · date de vente du portail · EUR · aucun solde retirable ni date de validation supposée.',
            'start': begin.isoformat(), 'end': finish.isoformat(), 'today': today.isoformat(),
            'total_cents': total, 'daily': daily, 'partners': partners, 'accounts': coverage,
            'included_partners': sum(p['cents'] is not None for p in partners), 'total_partners': len(partners),
            'partial': any(not s['eligible'] for s in sources) or any(d['status'] != 'complete' for d in daily),
            'comparisons': {'previous': comparison([d-timedelta(days=len(days)) for d in days]),
                            'year': comparison([previous_year(d) for d in days])}}
