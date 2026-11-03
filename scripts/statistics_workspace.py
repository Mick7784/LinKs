"""Read-only statistics projection. No collection, rewrites or partner requests.

counts.day is the historical local collection date, not a UTC timestamp. Never
re-localize it: the original UTC instants are not available for page counters.
"""
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
    first = min(start, yesterday).isoformat()
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
          AND c.kind IN ('view','click','tracked','story')
        GROUP BY c.day,c.kind,c.source,identity,label
    """, (first, end, detail_start.isoformat(), day)).fetchall()
    categories = {"view": "visits", "click": "public", "tracked": "tracked", "story": "campaigns"}
    by_day = {}
    series = {}
    cursor = start
    while cursor <= today:
        series[cursor.isoformat()] = dict(day=cursor.isoformat(), visits=0, public=0, tracked=0, campaigns=0)
        cursor += timedelta(days=1)
    campaign_by_id = {row["id"]: row for row in campaigns}
    detail_series = {}
    cursor = detail_start
    while cursor <= chosen:
        detail_series[cursor.isoformat()] = dict(day=cursor.isoformat(), visits=0, public=0, tracked=0, campaigns=0)
        cursor += timedelta(days=1)
    for row in rows:
        category = categories[row["kind"]]
        if row["day"] in series:
            series[row["day"]][category] += row["total"]
        if row["day"] in detail_series:
            detail_series[row["day"]][category] += row["total"]
        if row["day"] not in {day, end, yesterday.isoformat()}:
            continue
        source = row["source"] or "unknown"
        identity = source if category == "visits" else row["identity"]
        if category == "public":
            identity = aliases.get(identity, identity)
        historical_title = identity if category == "public" and identity and not identity.startswith(('block:', 'button:')) else None
        title = (labels.get(identity, historical_title) if category == "public" else row["label"]) or "Élément historique non identifié"
        if category == "visits":
            title = source
        items = by_day.setdefault(row["day"], {}).setdefault(category, {})
        item = items.setdefault(identity, {"id": identity, "name": title, "total": 0, "sources": {}})
        item["total"] += row["total"]
        item["sources"][source] = item["sources"].get(source, 0) + row["total"]
        if category == "campaigns":
            item["status"] = campaign_by_id.get(identity, {}).get("status", "Historique")

    def detail(key, category):
        items = sorted(by_day.get(key, {}).get(category, {}).values(), key=lambda item: (-item["total"], item["id"]))
        totals = {}
        for item in items:
            for source, count in item["sources"].items():
                totals[source] = totals.get(source, 0) + count
        return {"items": items, "sources": totals, "total": sum(totals.values())}

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
            "series": list(series.values()), "detail_series": list(detail_series.values()), "sources": sources}
