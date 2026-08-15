---
name: python-backend
description: Building and refining Python backends for readability above all — survey existing code and delete dead code before adding new, keep call chains shallow and folders flat, thin routes over one meaningful layer. Covers FastAPI project structure, Pydantic v2 schemas, dependency injection, async handlers, auth, transactional service layers, and testing with httpx/pytest, plus reduction passes that remove dead and duplicate code, collapse pass-through layers, and apply Pythonic idioms. Use when writing, reviewing, or refactoring FastAPI/Django/Flask code, Pydantic schemas, dependencies, service layers, or backend tests.
metadata:
  origin: merged
  sources:
    - name: fastapi-patterns
      url: https://github.com/affaan-m/ECC/blob/main/skills/fastapi-patterns/SKILL.md
    - name: python-simplifier
      url: https://github.com/citadelgrad/scott-cc/blob/main/skills/python-simplifier/SKILL.md
      license: MIT
---

# Python Backend

Production-grade Python backend work in two modes. Both share the same principles; pick by what the task asks for.

- **Building** — new app, new endpoint, new schema, new test. Survey the existing code first, then follow the structural patterns and copy from the references.
- **Refining** — reviewing or refactoring code that already works. Delete what is dead, remove duplication, apply idioms — preserving behavior exactly.

Neither mode is purely additive. Building includes deleting what the new code supersedes; a feature is not done while the path it replaced is still in the tree.

Refining never changes *what* the code does, only *how*. If a refactor would alter behavior, stop and ask. Removing provably dead code is not an exception to this — behavior nothing can reach is not behavior.

---

## Core Principles

### 1. Readability is the goal — everything below serves it

Code is read far more often than it is written. The two things that most damage readability in Python backends are **deep call chains** and **deep folder trees**, because both force the reader to hold a stack in their head while hunting across files. Keep both shallow.

**Shallow call chains.** A reader should get from HTTP request to the SQL it runs in one or two hops:

```python
# Bad: five frames, each one a redirect that adds nothing.
route -> UserController -> UserService -> UserManager -> UserRepository -> UserDAO -> db

# Good: two frames, each doing real work.
route -> UserService -> db
```

Every layer must justify itself by doing something — validating, deciding, owning a transaction. A layer that only forwards its arguments to the next layer is not architecture, it's a detour. Delete it and call through.

Practical limits, applied with judgment rather than counted mechanically:

- **Two hops** from route handler to database is the target; three needs a reason you can state
- **Don't wrap a wrapper** — if a method's body is a single delegating call, inline it
- **Prefer a function to a class** when there is no state to hold; a module-level function is one less indirection than a class you must construct to call
- **Prefer a direct call to a dynamic one** — registries, plugin dispatch, and `getattr` indirection defeat both the reader and go-to-definition
- **No inheritance for reuse** past one level; a shared function beats a base class the reader has to go read

**Flat folders.** Reach for a subdirectory when a flat file gets unwieldy, not in advance. A backend that fits in five files should be five files. Nesting a directory per entity across `routers/`, `models/`, `schemas/`, and `services/` means one conceptual change touches four folders — and the reader opens four to understand one thing. Start flat, split along the axis that is actually growing. See [references/fastapi-structure.md](references/fastapi-structure.md) for the flat-first layout and when to grow out of it.

### 2. Subtract before you add

Every task starts by reading what is already there. The best implementation of a feature is often mostly deletion, and the second best reuses something that already exists. Writing new code without that survey is how a codebase accumulates three functions that do the same thing.

**Before writing anything:**

- Search for an existing helper, service method, or schema that already does this — extending one beats adding a parallel one
- Find the nearest analogous feature and follow its shape, so the codebase stays learnable
- Notice what the change makes obsolete — a new code path often orphans the old one

**Always remove dead code you encounter.** Not as a separate cleanup ticket, as part of the change:

- Unreachable branches, and conditions that can no longer be false
- Functions, classes, and schemas with no remaining callers
- Imports, constants, and settings nothing reads
- Commented-out blocks — git remembers them, the file doesn't need to
- Compatibility shims for versions the project no longer supports
- Endpoints and feature flags for shipped or abandoned work

**Prefer the change that shrinks the diff.** A net-negative line count is a good outcome, not a suspicious one. When two implementations work, take the shorter one — unless the shorter one is the clever one, in which case principle 4 wins.

**But verify death before declaring it.** Python hides callers from grep, and this is where "delete it" goes wrong. Treat as live until proven otherwise: decorator-registered functions (routes, Celery tasks, pytest fixtures, SQLAlchemy event listeners, CLI commands), anything in `__all__` or imported for its side effects, names reached via `getattr`/registries/string config, Alembic migrations, and code called only from tests or other repos. See [references/dead-code-removal.md](references/dead-code-removal.md) for how to check.

Deletion is the one exception to "preserve functionality exactly" — removing genuinely dead code preserves behavior by definition. If you cannot prove it's dead, say so and leave it rather than guessing.

### 3. Thin routes, one meaningful layer behind them

Route handlers parse input, delegate, and map domain errors to HTTP status codes. Nothing else. Business logic, database mutations, and transaction boundaries live *one* layer down.

That layer is a service **or** a repository — not both stacked. Two names for the same hop is the most common way this pattern turns into the call chain principle 1 warns about. Add the second only when something concrete needs it (swapping the storage backend, sharing queries across several services), and say what that something is.

- **FastAPI**: thin handlers, logic in a service module
- **Django**: fat models, thin views; use managers and querysets — the manager *is* the layer, don't add a service on top
- **Flask**: blueprints for organization, thin routes

### 4. Remove duplicate code (DRY)

The primary target of any refinement pass. Actively hunt for repeated blocks across functions and modules, similar logic in multiple places, copy-pasted validation or transformation, and duplicated queries or API calls. See [references/deduplication-patterns.md](references/deduplication-patterns.md).

Wait for **3+** similar occurrences before extracting an abstraction. Two is a coincidence.

### 5. KISS

Straightforward over clever. One function, one job. A function past ~20 lines usually wants splitting — but split it into siblings the caller invokes in sequence, not into a chain where each helper calls the next. Splitting for length while deepening the stack trades one readability problem for a worse one. Avoid speculative abstraction.

### 6. Pythonic

PEP 8, standard library first, readability over brevity, explicit over implicit. Comprehensions, `any`/`all`, unpacking, f-strings, dataclasses, enums — see [references/pythonic-idioms.md](references/pythonic-idioms.md).

### 7. Async all the way down

Sync database calls inside `async def` block the event loop. Use async SQLAlchemy (`await db.execute(select(...))`), async sessions, and `ASGITransport` in tests.

### 8. No hardcoded values

No URLs, credentials, or magic numbers inline. Use `pydantic-settings`, environment variables, or module-level `UPPER_CASE` constants.

### 9. No silent failures

Never add a broad `try`/`except` that masks errors. Catch specific exceptions, fail fast, surface the unexpected. Ask before introducing any fallback behavior.

### 10. Always declare a typed `response_model`

Prevents accidental PII leaks and produces clean OpenAPI output.

---

## Anti-Patterns

```python
# Bad: a pass-through layer. UserManager adds a frame and a file, and does nothing.
class UserManager:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    async def get(self, user_id: int) -> User | None:
        return await self.repo.get(user_id)          # forwards, decides nothing

class UserService:
    async def get(self, user_id: int) -> User | None:
        return await self.manager.get(user_id)       # forwards again

# Good: the layer that survives is the one that owns the transaction and the rules.
class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)


# Bad: business logic inside the route handler.
@router.post("/users/")
async def create_user(payload: UserCreate, db: DbDep):
    hashed = bcrypt.hash(payload.password)
    user = User(email=payload.email, hashed_password=hashed)
    db.add(user)
    await db.commit()
    return user

# Good: thin route, transactional service, domain error mapped to HTTP.
@router.post("/users/", response_model=UserResponse, status_code=201)
async def create_user(payload: UserCreate, db: DbDep):
    try:
        return await UserService(db).create(payload)
    except DuplicateUserError:
        raise HTTPException(status_code=400, detail="Email already registered")


# Bad: sync DB calls in async routes block the event loop.
@router.get("/items/")
async def list_items(db: Session = Depends(get_db)):
    return db.query(Item).all()

# Good: async SQLAlchemy execution.
@router.get("/items/")
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item))
    return result.scalars().all()


# Bad: mutable default argument, shared across every call.
def append_to(element, target=[]):
    target.append(element)
    return target

# Good: None sentinel.
def append_to(element, target=None):
    if target is None:
        target = []
    target.append(element)
    return target
```

---

## What NOT to Do

1. **Don't add logging everywhere** — only where it earns its place
2. **Don't blanket-annotate internals** — public API surfaces and Pydantic schemas are always typed; for internal helpers add hints where they clarify, and let inference handle the obvious
3. **Don't over-document** — comments explain *why*, not *what*
4. **Don't abstract for a single use** — wait for 3+ similar patterns
5. **Don't handle impossible states** — trust your types and validation
6. **Don't use bare `except:`** — always catch specific exceptions
7. **Don't use mutable default arguments** — use the `None` sentinel
8. **Don't precheck for uniqueness** — rely on the DB's unique constraint and catch `IntegrityError`; a `SELECT`-then-`INSERT` check is race-prone
9. **Don't add a layer without a job** — if it only forwards arguments, delete it and call through
10. **Don't create a folder for one file** — a directory holding a single module is a rename waiting to happen
11. **Don't split a package by kind when it's small** — `user.py` holding that entity's schema, service, and routes beats four one-class files in four folders
12. **Don't leave the old path behind** when a new one replaces it — two ways to do one thing is worse than either
13. **Don't keep code "in case we need it later"** — that is what version control is for
14. **Don't delete what you only suspect is unused** — prove it or say you couldn't

---

## Process

**Building:**

1. **Survey first** — read the nearest existing feature. What can be extended instead of added? What does this change make obsolete?
2. Start in the flattest file that fits — schema, then service, then route
3. Split to a new module only once the current one is genuinely hard to navigate
4. Wire dependencies through `Annotated` type aliases — `DbDep`, `CurrentUserDep`
5. Write the test alongside, not after
6. **Sweep before finishing** — delete what the change orphaned, and any dead code you passed through on the way
7. Trace one request end to end and count the frames; if it's more than two meaningful hops, collapse before moving on

**Refining:**

1. **Read** the code and understand it before proposing anything
2. **Delete first** — dead code costs nothing to remove and shrinks everything downstream; simplifying code that should not exist is wasted effort
3. **Identify** violations against the principles above — trace the deepest call chain and the deepest folder path, since those cost the most to read
4. **Change minimally** — no scope creep
5. **Verify syntax** — `python -m py_compile <file>`
6. **Run tests** — `pytest`
7. **Check types** — `mypy`, if the project uses it; `ruff check` catches imports orphaned by deletions

Keep deletions in their own commit, separate from behavior changes — it makes both halves reviewable.

---

## Reference Files

- [references/fastapi-structure.md](references/fastapi-structure.md) — project layout, app factory + lifespan, `pydantic-settings` config, Pydantic v2 schemas, dependency injection, routers, service layer
- [references/fastapi-testing.md](references/fastapi-testing.md) — `httpx` + `pytest-asyncio` fixtures, in-memory DB, dependency overrides, auth fixtures
- [references/dead-code-removal.md](references/dead-code-removal.md) — finding dead code, what looks unreferenced but is live, verifying a deletion, reducing without deleting
- [references/deduplication-patterns.md](references/deduplication-patterns.md) — shared functions, dependency extraction, base classes, parameterized queries, context managers
- [references/pythonic-idioms.md](references/pythonic-idioms.md) — comprehensions, builtins, walrus, unpacking, f-strings, dataclasses, enums
- [references/django-flask-patterns.md](references/django-flask-patterns.md) — QuerySet-level filtering, custom managers, blueprint organization

---

## Best Practices

- Consolidate dependency injection via type aliases: `DbDep = Annotated[AsyncSession, Depends(get_db)]`
- Keep transaction boundaries inside the service layer, catching `IntegrityError` at the mutation site
- Parse JWT claims defensively — `sub` arrives as a string, cast explicitly and catch the cast failure
- Enforce deterministic ordering (`.order_by(Model.id)`) on every offset/limit paginated endpoint, or rows will skip between pages
- Separate authorization from authentication dependencies so `401` and `403` stay distinguishable
- Unique-constraint handling requires an actual unique index (`unique=True` on the mapped column); without it, catching `IntegrityError` protects nothing

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Refactoring everything at once | DRY first, then idioms |
| Adding abstractions for 1–2 uses | Wait for 3+ occurrences |
| Changing behavior while simplifying | Only change *how*, never *what* |
| Bare `except:` | Catch specific exceptions |
| Mutable default arguments | `None` sentinel |
| Over-typing simple internals | Let inference work |
| Writing new code without reading the old | Survey first; extend what exists |
| Leaving the superseded path in place | Delete it in the same change |
| Commented-out code "just in case" | Delete; git has it |
| Deleting on a grep miss alone | Check decorators, `__all__`, string references |
| Treating uncovered lines as unused | Coverage is a hint, not proof |
| Layer that only forwards its arguments | Delete it, call through |
| Service *and* repository for one hop | Pick one until the second earns itself |
| A folder per entity per kind | Flat modules; split along the axis that's growing |
| Class with no state, only methods | Module-level functions |
| Helper chains created to shorten a function | Sibling calls from one caller, not a stack |
| Sync ORM calls in `async def` | Async engine, `await db.execute(...)` |
| Paginating without `order_by` | Explicit deterministic sort |
| `class Config` on Pydantic models | v2 uses `model_config = {...}` |

---

## Limitations

- Framework guidance is opinionated (FastAPI-first, with Django/Flask secondary) — verify it matches the project's existing conventions before applying
- Refinement preserves functionality; it does not add features or fix bugs. Deleting dead code is in scope; deleting code that is merely untested, undocumented, or unfamiliar is not
- Dead-code detection is heuristic in Python. `ruff`, `vulture`, and coverage produce candidates, not verdicts — the burden of proof stays with the deletion
- Does not replace running tests and type checkers after changes
- The reference layouts show a multi-entity ORM app at its grown-out size; that is the destination, not the starting point — smaller or single-table services take the schema/DI/testing patterns and skip the scaffolding
- "Shallow" is a judgment call, not a lint rule. A third hop that owns a real boundary — a transaction, an external API, a permission decision — is worth its frame. The test is whether you can say what the layer decides
- Stop and ask when the codebase structure, framework choice, or refactoring scope is unclear
