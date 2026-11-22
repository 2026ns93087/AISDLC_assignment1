# Quickstart: Smart Todo CLI

**Date**: 2026-11-22 | **Contract**: [contracts/cli-contract.md](contracts/cli-contract.md)

This is the manual validation path for SC-004. Run from `Part-1A/` once the code exists.

```powershell
$env:PYTHONPATH = "src"
$env:TODO_NOW = "2026-01-01T09:00:00Z"
python -m smart_todo --file demo.json add --title "Buy milk" --priority high --tag home
python -m smart_todo --file demo.json add --title "Write report" --tag work
python -m smart_todo --file demo.json list --sort priority
python -m smart_todo --file demo.json status 1 in_progress
python -m smart_todo --file demo.json status 1 done
python -m smart_todo --file demo.json edit 1 --title "X"      # fails: TASK_LOCKED
python -m smart_todo --file demo.json delete 2
```

Expected: the first `add` prints the object from AC-001 with `priority` `high` and `tags`
`["home"]`; `edit` on a done task exits 1 with `TASK_LOCKED` on stderr.

Harness run (after Phase 4): `python .harness/run_harness.py`.
