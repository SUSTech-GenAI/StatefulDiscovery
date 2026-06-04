---
name: repro-gate-check
description: Invoke before final output. Validates that all claims have reproducible evidence (code files exist, experiment records complete). Run the bundled Python script.
---

# ReproGate Check

Run the check script directly:

```bash
python3 /home/agent/.claude/skills/repro-gate-check/scripts/check_repro_gate.py /workspace/run /workspace/run/claims.json
```

If any claim fails, fix the issue or discard the claim.
