#!/usr/bin/env python3
"""One-shot backfill: populate demo TodayPage from existing analysis blobs.

Creates SignalEvent rows + backfills lead intelligence from the latest
completed analysis for the HiMeetAI demo company.
"""
import json
import sqlite3
import uuid
from datetime import UTC, datetime

DB_PATH = "gtm_dev.db"

CATEGORY_MAP = {
    "trend": "market_trend",
    "opportunity": "market_trend",
    "threat": "competitor_news",
    "regulation": "regulation",
    "news": "general_news",
    "market": "market_trend",
    "general": "general_news",
    "market_analysis": "market_trend",
}

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Find demo company
row = c.execute(
    "SELECT id FROM companies WHERE name LIKE '%Hi Meet%' OR name LIKE '%HiMeet%' LIMIT 1"
).fetchone()
if not row:
    print("No HiMeetAI company found")
    exit(1)
company_id = row[0]
print(f"Company: {company_id[:12]}...")

# Pick the analysis with the most data (not just the latest)
arow = c.execute(
    "SELECT market_insights, competitor_analysis, leads "
    "FROM analyses WHERE company_id = ? AND status = 'COMPLETED' "
    "ORDER BY length(COALESCE(market_insights,'')) + length(COALESCE(competitor_analysis,'')) DESC "
    "LIMIT 1",
    (company_id,),
).fetchone()
if not arow:
    print("No completed analysis found")
    exit(1)

market_insights = json.loads(arow[0]) if arow[0] else []
competitor_analysis = json.loads(arow[1]) if arow[1] else []
leads_blob = json.loads(arow[2]) if arow[2] else []
now = datetime.now(UTC).replace(tzinfo=None).isoformat()

print(f"Market insights: {len(market_insights)}, Competitors: {len(competitor_analysis)}, Leads: {len(leads_blob)}")

# Clear old analysis-sourced signals
c.execute(
    "DELETE FROM signal_events WHERE company_id = ? AND source = 'analysis'",
    (company_id,),
)

# Bridge market insights → signals
for mi in market_insights:
    sig_type = CATEGORY_MAP.get((mi.get("category") or "general").lower(), "general_news")
    confidence = mi.get("confidence", 0.0)
    urgency = "this_week" if confidence >= 0.7 else ("this_month" if confidence >= 0.4 else "monitor")

    findings = (mi.get("key_findings") or [])[:3]
    implications = (mi.get("implications") or [])[:2]
    summary_extra = " | ".join(findings + implications)
    summary = (mi.get("summary") or "") + ("\n" + summary_extra if summary_extra else "")

    recs = mi.get("recommendations") or []
    rec_action = "; ".join(recs[:2]) if recs else None

    c.execute(
        "INSERT INTO signal_events "
        "(id, company_id, signal_type, urgency, headline, summary, source, "
        "relevance_score, recommended_action, competitors_mentioned, is_actioned, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,0,?)",
        (
            str(uuid.uuid4()), company_id, sig_type, urgency,
            mi.get("title", "Untitled"), summary,
            "analysis", confidence,
            rec_action, "[]", now,
        ),
    )

print(f"Created {len(market_insights)} market signals")

# Bridge competitor analysis → signals
for comp in competitor_analysis:
    name = comp.get("competitor_name", "Unknown")
    headline_extra = ""
    if comp.get("strategic_moves"):
        headline_extra = comp["strategic_moves"][0]
    elif comp.get("recent_news"):
        headline_extra = comp["recent_news"][0]
    else:
        headline_extra = (comp.get("positioning") or comp.get("description", ""))[:100] or "competitor identified"

    headline = f"{name} — {headline_extra}"

    lines = []
    if comp.get("strengths"):
        lines.append("Strengths: " + ", ".join(comp["strengths"][:3]))
    if comp.get("weaknesses"):
        lines.append("Gaps: " + ", ".join(comp["weaknesses"][:3]))
    if comp.get("key_differentiators"):
        lines.append("Differentiators: " + ", ".join(comp["key_differentiators"][:3]))

    confidence = comp.get("confidence", 0.0)
    urgency = "this_week" if confidence >= 0.7 else "this_month"

    c.execute(
        "INSERT INTO signal_events "
        "(id, company_id, signal_type, urgency, headline, summary, source, "
        "relevance_score, competitors_mentioned, recommended_action, is_actioned, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,0,?)",
        (
            str(uuid.uuid4()), company_id, "competitor_news", urgency,
            headline, "\n".join(lines) or comp.get("description", ""),
            "analysis", confidence,
            json.dumps([name]),
            f"Review {name}'s positioning and adjust your differentiation strategy.",
            now,
        ),
    )

print(f"Created {len(competitor_analysis)} competitor signals")

# Backfill lead intelligence
updated = 0
for ld in leads_blob:
    company_name = ld.get("company_name", "")
    if not company_name:
        continue
    pain_points = json.dumps(ld.get("pain_points") or [])
    trigger_events = json.dumps(ld.get("trigger_events") or [])
    recommended_approach = ld.get("recommended_approach") or ""

    # Match by first 30 chars of company name
    c.execute(
        "UPDATE leads SET pain_points = ?, trigger_events = ?, recommended_approach = ? "
        "WHERE company_id = ? AND lead_company_name LIKE ? AND pain_points IS NULL",
        (pain_points, trigger_events, recommended_approach, company_id, f"%{company_name[:30]}%"),
    )
    updated += c.rowcount

print(f"Updated {updated} leads with intelligence")

conn.commit()

# Verify
sigs = c.execute("SELECT COUNT(*) FROM signal_events WHERE company_id = ?", (company_id,)).fetchone()[0]
leads_with_triggers = c.execute(
    "SELECT COUNT(*) FROM leads WHERE company_id = ? AND trigger_events IS NOT NULL AND trigger_events != '[]'",
    (company_id,),
).fetchone()[0]
sample = c.execute(
    "SELECT headline, signal_type FROM signal_events WHERE company_id = ? LIMIT 3",
    (company_id,),
).fetchall()

print(f"\nFinal: {sigs} signals, {leads_with_triggers} leads with trigger events")
for s in sample:
    print(f"  [{s[1]}] {s[0][:80]}")

conn.close()
