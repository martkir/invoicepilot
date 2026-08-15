---
description: >-
  Finding and safely removing dead Python code: search techniques, the tools
  worth running, what looks unreferenced but is live (decorators, registries,
  __all__, migrations), and how to verify a deletion.
metadata:
  tags: [python, dead-code, deletion, refactoring, vulture, ruff, cleanup]
---

# Dead Code Removal

Deleting code is the highest-leverage edit available: it removes a maintenance burden, a reading cost, and a place for bugs to hide, all at once. It is also the edit most likely to break something invisibly, because Python resolves plenty of calls in ways `grep` cannot see.

The rule: **delete aggressively, but prove death first.**

## Finding Candidates

Cheap sweeps, roughly in order of signal:

```bash
# Unused imports, variables, and unreachable code — fast, high precision
ruff check --select F401,F811,F841,ARG,ERA .

# Whole unused functions/classes/attributes — noisier, needs review
uvx vulture . --min-confidence 80

# Coverage as a dead-code hint: lines the full test suite never reaches
pytest --cov=app --cov-report=term-missing

# Callers of a specific name, including string references
rg -n --word-regexp 'process_legacy_invoice'
rg -n 'process_legacy_invoice'   # unquoted AND quoted, catches config/getattr use
```

`ERA001` (commented-out code) is worth enabling permanently — it catches the commented block that would otherwise sit there for years.

Coverage is a **hint**, never proof. Untested is not the same as unused; that distinction is exactly what the next section is about.

## Looks Dead, Is Live

Python's dynamism means these have no direct caller in the source and are still very much running. Treat each as live until you have positive evidence otherwise:

| Pattern | Why grep misses it |
|---|---|
| `@app.get(...)` / `@router.post(...)` handlers | Called by the framework, never by name |
| `@celery.task`, `@shared_task`, APScheduler jobs | Dispatched by name from a queue, often a string |
| Pytest fixtures, `conftest.py` contents | Resolved by argument name |
| `@event.listens_for`, signals, `__init_subclass__` | Registered by import side effect |
| Alembic migrations | Run by revision id; deleting rewrites history |
| Pydantic validators, `model_config` hooks | Invoked by the metaclass |
| Names in `__all__` or re-exported in `__init__.py` | Part of the public API for other repos |
| `getattr(module, name)`, plugin registries, `entry_points` | Name lives in a string or config file |
| Enum members persisted to the database | Rows still hold the value |
| Exception classes | Raised in one place, caught in another via `except` |
| Settings fields | Read from `.env` or deployment config, not code |
| Abstract-method implementations | Called through the base class |
| Code used only by tests | Dead product code, live test dependency — decide deliberately |

For anything in this table, verification means checking the *registration* mechanism, not the call site: is the module still imported, is the route still mounted, is the task name still enqueued anywhere, does the config still name it.

## Verifying a Deletion

1. **Search both forms** — bare identifier and quoted string. Config, `getattr`, and task routing hide names in strings.
2. **Search beyond the repo** if this is a library or shared service; a public name has callers you cannot see. If in doubt, deprecate rather than delete.
3. **Check the entrypoints** — is the containing module still imported at all? An orphaned module makes everything in it dead at once, which is a much cleaner deletion than picking off functions.
4. **Delete the whole cluster** — a dead function usually takes its tests, schemas, fixtures, imports, settings keys, and error classes with it. Leaving those behind converts one piece of dead code into five.
5. **Run the suite** — `pytest`. Then `ruff check` and `mypy` to catch imports and annotations that referenced the deleted name.
6. **Commit deletions separately** from behavior changes. A pure-deletion commit is trivial to review and trivial to revert, which is what makes aggressive deletion safe.

## What Not to Delete

- Code you merely *suspect* is unused — say what you found and leave it, or ask
- Anything whose only evidence of death is low test coverage
- Public API surface of a library, without a deprecation path
- Alembic migrations, ever, once they have run anywhere real
- Error handling for states you believe are impossible — that belief is not evidence, and this is a behavior change rather than a deletion

## Reducing Without Deleting

Not every reduction is a removal. Also worth doing on every pass:

- Replace a hand-rolled helper with the stdlib or framework equivalent that already exists
- Collapse a pass-through layer — pure indirection, bought nothing (see [../SKILL.md](../SKILL.md))
- Let Pydantic validate instead of hand-written `if not data.get(...)` chains
- Let the database filter, sort, and count instead of Python loops over full result sets
- Replace a parallel implementation with a parameter on the existing one — see [deduplication-patterns.md](deduplication-patterns.md)
- Drop defensive checks that duplicate a schema constraint already enforced upstream
