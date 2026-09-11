# Contributing to AquaReserve
This is a solo project, but it follows a team-style workflow so the process is auditable and mirrors professional practice.

## Workflow
1. **Branch** off `main`: `feat/<short-name>`, `fix/<short-name>` or `docs/<short-name>`.
2. **Implement** behind config - no hard-coded agronomic constants; add/extend YAML schema instead.
3. **Test** add unit/integration tests; keep CI green. 
4. **Open a PR** into `main`. The PR description links the backlog story (e.g. *D2*) and notes what was tested.
5. **Self-review** against the checklist below, then squash-merge once CI is green.

## Local Checks

```bash
pip install -e ".[dev]"
ruff check src tests
python -m aquareserve.cli validate
pytest --cov=aquareserve
```

## PR Checklist

- [X] Linked to a backlog story / task-board card.
- [X] Behaviour covered by tests; CI green (lint + validate + tests).
- [X] New config options documented in the relevant YAML + schema docstrings.
- [X] Design/architecture changes reflected in `docs/DESIGN_AND_TESTING.md`.
- [X] No secrets, large data files or generated artifacts committed.

## Definition of Done

See `docs/PROJECT_PLAN.md` §8.
