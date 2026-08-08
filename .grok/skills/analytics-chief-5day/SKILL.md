---
name: analytics-chief-5day
description: FlowChartCharter Analytics Chief capstone — 5-day end-of-week audit, moving-average trends, RosterRecommendationDossier, cheat-code extraction into Muscle-Memory, Monday Sync executes Board dossier (no GM guessing). Triggers on analytics chief, 5-day protocol, end of week, dossier, cheat code extraction.
---

# Analytics Chief — 5-Day Protocol

**Day-to-day** = Boss Agent (GM). **Macro trends** = Analytics Chief.

## Cadence
1. Each charter → `ingest_cycle` (immutable snapshots)
2. Each day close → `close_day`
3. Day 5 → `execute_end_of_week_audit()` → dossier + cheat codes
4. Monday → GM `monday_morning_sync(dossier=...)` **executes**, does not guess

## Dossier
- 5-day MA fitness / quality / tokens / risk
- PROMOTE | TERMINATE | DEMOTE | RETAIN with confidence + rationale
- Cheat codes: runs that beat expected cost/latency → Muscle-Memory + Living Playbook

## API
```python
system.advance_analytics_day()
system.run_end_of_week_protocol(force=True)
# or automatic via downtime_sync after 5 days
```
