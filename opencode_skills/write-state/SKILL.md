---
name: write-state
description: Invoke for epistemic_state.json format reference. Defines the global exploration state schema with L1/L2 uncertainty assessment.
---

# epistemic_state.json Format

Write to `/workspace/run/epistemic_state.json`. This is your cognitive state — "what do I know, what don't I know, how certain am I". Updated after each experiment cycle.

This file is NOT a progress dashboard. It is where you reason explicitly about your uncertainty and what actions would reduce it most.

## Schema

### `data_context` (written once after EDA, not updated later)

| Field | Type | Description |
|-------|------|-------------|
| `variables` | array of strings | All column names across dataset files |
| `observation_counts` | object | Mapping of dataset/group name to row count |
| `key_characteristics` | string | Summary of the dataset's nature, domain, and structure |
| `initial_observations` | array of strings | Specific findings from EDA and base experiments |

### `exploration_progress` (updated each cycle — bookkeeping counters)

| Field | Type | Description |
|-------|------|-------------|
| `phase` | string | One of: `base`, `exploring`, `finalizing` |
| `cycle_id` | integer | Current cycle number |
| `patterns_total` | integer | Total patterns discovered |
| `patterns_unexplained` | integer | Patterns with status `unexplained` |
| `patterns_explained` | integer | Patterns with status `explained` |
| `investigations_total` | integer | Total investigations created |
| `investigations_active` | integer | Investigations with status `active` |
| `investigations_resolved` | integer | Investigations with status `resolved` |
| `investigations_retired` | integer | Investigations with status `retired` |
| `experiments_used` | integer | Total experiments run (base + exploration) |
| `budget_total` | integer | Max experiments from task_packet budget |
| `budget_remaining` | integer | budget_total - experiments_used |

### `active_focus` (updated each cycle — quick-glance summary)

| Field | Type | Description |
|-------|------|-------------|
| `investigation_id` | string or null | Currently active investigation, null during base phase or between investigations |
| `frontier_summary` | string | One sentence: the most important unresolved question right now and why it's the priority |
| `current_risks` | array of strings | Active risks of misinterpretation, bias, or confounding to keep in mind |

This section is a compact summary for quick orientation — especially useful after context compaction. The real reasoning lives in level1/level2/meta_uncertainty below.

### `level1` — Exploration Space Assessment (updated each cycle)

Answers: Is the exploration space still open? Should I branch or deepen?

| Field | Type | Description |
|-------|------|-------------|
| `frontier_status` | string | `open` / `narrowing` / `exhausted` — is there still unexplored territory worth pursuing? |
| `saturation_assessment` | string | `low` / `medium` / `high` — are new experiments still producing new patterns or insights? |
| `saturation_rationale` | string | WHY this saturation level — are recent cycles yielding diminishing returns? |
| `recommended_mode` | string | `branch` / `deepen` / `switch` / `stop` — what should the next cycle prioritize? |

**How to assess**: Look at unexplained patterns and their priorities. Consider whether recent investigations produced new patterns from residuals. High-priority unexplained patterns → frontier is open. Multiple cycles without new patterns → high saturation.

### `level2` — Active Investigation Resolution Assessment (updated each cycle)

Answers: How resolved is the current investigation? How strong is the evidence? What's the biggest red flag?

| Field | Type | Description |
|-------|------|-------------|
| `active_investigation_id` | string or null | Currently active investigation, null if between investigations |
| `resolution_status` | string | `open` / `partially_resolved` / `resolved` / `inconclusive` — from judge's adjudication |
| `resolution_confidence` | number | 0-1, your confidence in the resolution — synthesize judge's confidence with your own assessment |
| `resolution_rationale` | string | WHY this confidence — what evidence supports it, what's still missing |
| `evidence_strength` | string | `weak` / `moderate` / `strong` — overall evidence quality for this investigation |
| `red_flag_pressure` | string | `low` / `medium` / `high` — severity of unresolved red flags or concerns |
| `next_best_resolution_step` | string | If the investigation is not resolved, what single experiment would most reduce uncertainty? Empty if resolved. |

**How to assess**: Read `claim_scores.json` for judge's evaluation. If judge flagged red flags → high red_flag_pressure. If adjudication is `still_contested` → low resolution_confidence. If `remaining_uncertainties` are substantive → describe the best next step.

### `meta_uncertainty` — Why Am I Uncertain? (updated each cycle)

Answers: What is my biggest source of uncertainty right now? What action would most reduce it?

| Field | Type | Description |
|-------|------|-------------|
| `primary_uncertainty_type` | string | One of: `frontier` (unexplored space), `evidence` (weak/missing evidence), `artifact` (possible technical artifact), `boundary_condition` (finding may not generalize), `generalization` (unclear if pattern is real) |
| `primary_uncertainty_rationale` | string | WHY this is the primary uncertainty — be specific, reference patterns/investigations/evidence |
| `best_information_gain_opportunity` | string | The single action that would most reduce overall uncertainty right now |

**How to assess**: Consider L1 and L2 together.
- If L1 coverage is low and L2 is resolved → primary uncertainty is `frontier` (need to explore more)
- If L1 coverage is high but L2 has red flags → primary uncertainty is `artifact` or `evidence`
- If both are low → you're close to stopping

### `decision_log` (append-only)

Array of objects, one per cycle. Records the strategist's decision history.

| Field | Type | Description |
|-------|------|-------------|
| `cycle_id` | integer | Cycle number |
| `action` | string | The strategist action taken |
| `target` | object | `pattern_id` (string or null) and `investigation_id` (string or null) |
| `rationale` | string | Why this action was chosen |
| `outcome` | string | What happened (filled after the cycle completes) |
