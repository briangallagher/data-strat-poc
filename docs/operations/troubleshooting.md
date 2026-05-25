# Troubleshooting

Common failure modes, diagnostic commands, and recovery procedures. Updated as issues are encountered.

**Last Updated:** 2026-05-22 (M0 — initial structure)

## General Diagnostics

```bash
# Pod status
oc get pods -n data-strat-poc -o wide

# Events (recent failures)
oc get events -n data-strat-poc --sort-by='.lastTimestamp' | tail -20

# Pod logs
oc logs <pod-name> -n data-strat-poc

# Describe pod (for scheduling/resource issues)
oc describe pod <pod-name> -n data-strat-poc
```

## Known Issues

| Symptom | Cause | Fix | Milestone |
|---------|-------|-----|-----------|
| | | | |

<!-- Updated at each milestone checkpoint -->
