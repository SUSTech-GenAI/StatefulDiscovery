---
name: write-patterns
description: Invoke for patterns.json format reference. Defines the schema for tracking unexplained data patterns.
---

# patterns.json Format

Write to `/workspace/run/patterns.json`. This file tracks all discovered patterns — anomalies, structures, and associations found during EDA and experiments. Updated dynamically throughout exploration.

## Schema

Root object with a single `patterns` array.

### Pattern fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Pattern identifier (P1, P2, ...) |
| `observation` | string | yes | Specific, concrete description of the pattern. Must reference actual data values or statistics. |
| `source` | string | yes | Experiment ID that revealed this pattern (e.g. "base002", "exp003") or "eda" |
| `status` | string | yes | One of: `unexplained`, `partially_explained`, `explained` |
| `investigation_id` | string or null | yes | ID of the investigation addressing this pattern, or null if unattached |
| `related_variables` | array of strings | yes | Column names from the dataset involved in this pattern |
| `priority` | number | yes | 0 to 1. Based on anomaly strength, effect size, or scientific interest. Higher = more worth investigating. |

### Status transitions

- `unexplained` → `partially_explained`: some aspects addressed by an investigation but uncertainties remain
- `partially_explained` → `explained`: investigation has resolved the pattern with sufficient evidence
- `unexplained` → `explained`: directly resolved in one cycle

### When to update

- **Create patterns**: after EDA + base experiments (Phase 0), and after each experiment cycle when residuals or new anomalies emerge
- **Update status**: after judge evaluates an investigation — mark patterns as explained if the investigation's adjudication resolves them
- **Add new patterns**: from experiment residuals, unexpected findings, or anomalies in results
