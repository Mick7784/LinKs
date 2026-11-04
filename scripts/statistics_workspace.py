"""Read-only statistics projection. No collection, rewrites or partner requests.

counts.day is the historical local collection date, not a UTC timestamp. Never
re-localize it: the original UTC instants are not available for page counters.
"""
import json
from datetime import date, timedelta


def workspace(db, *, now, zone, selected, period, aliases, labels, campaigns, selection, sources):
    today = now.astimezone(zone).date()
    chosen = date.fromisoformat(selected) if selected else today
    if chosen > today:
        raise ValueError("La journée doit être antérieure ou égale à aujourd’hui")
    if chosen < date.min + timedelta(days=29):
        raise ValueError("La journée est trop ancienne pour afficher sa période")
    if period not in ("30", "month"):
        raise ValueError("Période attendue : 30 ou month")
    start = today.replace(day=1) if period == "month" else today - timedelta(days=29)
    yesterday = today - timedelta(days=1)
    duration = (today - start).days + 1
    previous_start = start - timedelta(days=duration)
    previous_end = start - timedelta(days=1)
    chosen_previous = (chosen - timedelta(days=1)).isoformat()
    first = previous_start.isoformat()
    day = chosen.isoformat()
    end = today.isoformat()
    detail_start = chosen - timedelta(days=29)
    # LEFT JOIN keeps orphaned historical events countable, under their captured
    # token identity. Missing metadata must not silently remove a contribution.
    rows = db.execute("""
        SELECT c.day,c.kind,c.source,
          CASE c.kind
            WHEN 'tracked' THEN COALESCE(t.link_id,substr(c.link,9,19))
            WHEN 'story' THEN COALESCE(s.promotion_id,substr(c.link,7,19))
            ELSE c.link END AS identity,
          CASE c.kind WHEN 'tracked' THEN l.name
            WHEN 'story' THEN COALESCE(b.internal_name,s.name) END AS label,
          SUM(c.total) AS total
        FROM counts c
        LEFT JOIN tracked_tokens t ON c.kind='tracked' AND substr(c.link,9,19)=t.token
        LEFT JOIN tracked_links l ON l.id=t.link_id
        LEFT JOIN story_links s ON c.kind='story' AND substr(c.link,7,19)=s.token
        LEFT JOIN content_blocks b ON b.id=s.promotion_id
        WHERE ((c.day BETWEEN ? AND ?) OR (c.day BETWEEN ? AND ?))
          AND c.kind IN ('view','click','tracked','story','promo_code_copy','impression')
        GROUP BY c.day,c.kind,c.source,identity,label
    """, (first, end, detail_start.isoformat(), day)).fetchall()
    categories = {"view": "visits", "click": "public", "tracked": "tracked", "story": "campaigns",
                  "promo_code_copy": "copies"}
    by_day = {}
    period_items = {key: {} for key in categories.values()}
    previous_items = {key: {} for key in categories.values()}
    day_performance, period_performance = {}, {}
    campaign_by_id = {row["id"]: row for row in campaigns}
    partner_links = {row['id']: row['partner_id'] for row in db.execute(
        "SELECT l.id,COALESCE(a.partner_id,'') partner_id FROM tracked_links l LEFT JOIN tracked_link_partners a ON a.link_id=l.id")}

    def add_performance(target, ident, source, metric, row, name):
        item = target.setdefault(ident, {'id':ident, 'name':campaign_by_id.get(ident, {}).get('internal_name') or name or 'Campagne historique', 'sources':{}})
        values = item['sources'].setdefault(source, {'impressions':0, 'clicks':0, 'copies':0})
        values[metric] += row['total']
    series = {}
    campaign_activity = {}
    preceding_visits = 0
    cursor = start
    while cursor <= today:
        series[cursor.isoformat()] = dict(day=cursor.isoformat(), visits=0, public=0, tracked=0, campaigns=0, copies=0,
                                          tracked_sources={})
        cursor += timedelta(days=1)
    detail_series = {}
    cursor = detail_start
    while cursor <= chosen:
        detail_series[cursor.isoformat()] = dict(day=cursor.isoformat(), visits=0, public=0, tracked=0, campaigns=0, copies=0)
        cursor += timedelta(days=1)
    for row in rows:
        source = row['source'] or 'unknown'
        snapshot = json.loads(row['identity']) if row['kind']=='promo_code_copy' else None
        public_id = aliases.get(row['identity'], row['identity'])
        performance_id = snapshot['id'] if snapshot else public_id[6:] if public_id.startswith('block:') else None
        performance_metric = {'impression':'impressions', 'click':'clicks', 'promo_code_copy':'copies'}.get(row['kind'])
        if row['kind']=='click' and performance_id not in campaign_by_id:
            performance_id = None
        if performance_id and performance_metric:
            if row['day']==day:
                add_performance(day_performance, performance_id, source, performance_metric, row, snapshot['name'] if snapshot else None)
            if start.isoformat()<=row['day']<=end:
                add_performance(period_performance, performance_id, source, performance_metric, row, snapshot['name'] if snapshot else None)
        if row['kind']=='impression':
            continue
        category = categories[row["kind"]]
        if row["day"] == previous_end.isoformat() and category == "visits":
            preceding_visits += row["total"]
        if row["day"] in series:
            summary = series[row["day"]]
            summary[category] += row["total"]
            if category == "tracked":
                counts = summary["tracked_sources"]
                counts[source] = counts.get(source, 0) + row["total"]
            elif category == "campaigns" and row["total"] > 0:
                daily = campaign_activity.setdefault(row["day"], {})
                item = daily.setdefault(row["identity"], {"id": row["identity"],
                    "name": row["label"] or "Élément historique non identifié", "total": 0})
                item["total"] += row["total"]
        if row["day"] in detail_series:
            detail_series[row["day"]][category] += row["total"]
        in_period = start.isoformat() <= row["day"] <= end
        in_previous = previous_start.isoformat() <= row['day'] <= previous_end.isoformat()
        if not in_period and not in_previous and row["day"] not in {day, chosen_previous, end, yesterday.isoformat()}:
            continue
        identity = source if category == "visits" else row["identity"]
        if snapshot is not None:
            identity = json.dumps([snapshot["id"], snapshot["code"]], ensure_ascii=False)
        if category == "public":
            identity = aliases.get(identity, identity)
        historical_title = identity if category == "public" and identity and not identity.startswith(('block:', 'button:')) else None
        title = (labels.get(identity, historical_title) if category == "public" else row["label"]) or "Élément historique non identifié"
        if category == "visits":
            title = source
        elif category == "copies":
            title = snapshot["name"] + " · " + snapshot["code"]
        targets = []
        if row["day"] in {day, chosen_previous, end, yesterday.isoformat()}:
            targets.append(by_day.setdefault(row["day"], {}).setdefault(category, {}))
        if in_period:
            targets.append(period_items[category])
        if in_previous:
            targets.append(previous_items[category])
        for items in targets:
            item = items.setdefault(identity, {"id": identity, "name": title, "total": 0, "sources": {}})
            if category == 'tracked' and identity in partner_links:
                item['partner_id'] = partner_links[identity]
            if category == "copies":
                item["code"] = snapshot["code"]
                item["campaign_name"] = snapshot["name"]
                item["campaign_id"] = snapshot["id"]
            item["total"] += row["total"]
            item["sources"][source] = item["sources"].get(source, 0) + row["total"]
            if category == "campaigns":
                item["status"] = campaign_by_id.get(identity, {}).get("status", "Historique")

    def detail(key, category):
        return summarize(by_day.get(key, {}).get(category, {}))

    def summarize(group):
        items = sorted(group.values(), key=lambda item: (-item["total"], item["id"]))
        totals = {}
        for item in items:
            for source, count in item["sources"].items():
                totals[source] = totals.get(source, 0) + count
        return {"items": items, "sources": totals, "total": sum(totals.values())}

    for key, summary in series.items():
        daily = campaign_activity.get(key, {})
        summary["campaign_count"] = len(daily)
        summary["top_campaigns"] = sorted(daily.values(), key=lambda item: (-item["total"], item["id"]))[:3]
        summary["previous_visits"] = preceding_visits
        preceding_visits = summary["visits"]

    overview = {key: detail(end, key) for key in categories.values()}
    campaign_counts = {item["id"]: item["total"] for item in overview["campaigns"]["items"]}
    active = [{"id": ident, "name": campaign_by_id[ident]["internal_name"],
               "total": campaign_counts.get(ident, 0)} for ident in selection["eligible_ids"][:3]]
    # Overview needs only aggregates, not thousands of duplicate item payloads.
    for value in overview.values():
        value.pop("items")
    return {"today": end, "date": day, "timezone": str(zone), "period": period,
            "from": start.isoformat(), "to": end, "overview": overview,
            "previous_visits": detail(yesterday.isoformat(), "visits")["total"],
            "active_campaigns": active, "active_count": len(selection["eligible_ids"]),
            "details": {key: detail(day, key) for key in categories.values()},
            "previous_details": {key: detail(chosen_previous, key) for key in categories.values()},
            "previous_period_details": {key: summarize(previous_items[key]) for key in categories.values()},
            "comparison": {"from":previous_start.isoformat(), "to":previous_end.isoformat(), "days":duration},
            "performance": list(day_performance.values()), "period_performance": list(period_performance.values()),
            "partners": [dict(row) for row in db.execute('SELECT id,name FROM affiliate_partners ORDER BY name')],
            "period_details": {key: summarize(period_items[key]) for key in categories.values()},
            "series": list(series.values()), "detail_series": list(detail_series.values()), "sources": sources}
