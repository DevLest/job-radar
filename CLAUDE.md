# AI System Prompt — Job Radar Development Rules & Standards

You are an AI coding assistant working on **Job Radar**, a personal job-search pipeline with a local web UI. Generate code that **strictly follows the rules, structure, and conventions below**.

Never violate these rules unless the user explicitly tells you to. If a request conflicts with them, ask before writing code.

> These rules mirror `.cursor/rules/*.mdc`. When you change one, update the other in the same commit.

---

# Tech Stack

* **Language:** Python 3.12+ (typed, `from __future__ import annotations`)
* **Web:** Flask 3 (server-rendered Jinja templates, localhost only)
* **UI:** Jinja macros + vanilla JS + plain CSS. **No build step, no frontend framework.**
* **UI architecture:** Atomic Design
* **Backend architecture:** Domain-Driven Design (by feature) + Clean Architecture, SOLID / SRP
* **Storage:** SQLite (`jobs.db`, WAL mode) through repositories
* **AI:** Anthropic SDK (`anthropic`), one wrapper in `lib/`
* **Other:** `httpx` (feeds), `pyyaml` (profile), `pypdf` / `python-docx` (CV), IMAP/SMTP (stdlib)
* **Run:** `start.bat`, or `.venv\Scripts\python run.py ui | run | alerts | fetch | score | updates | ...`

---

# Target Directory Structure

```text
run.py                          CLI entry: parses args, calls services only
jobradar/
  app.py                        Flask app factory: registers blueprints, filters, globals
  container.py                  Composition root: builds repositories/services/clients (DIP)

  domain/                       One folder per feature: never grouped by technical type
    jobs/
      job.py                    Entity: dataclass + behaviour (hide(), queue(), is_duplicate_of())
      job_repository.py         SQL for the `jobs` table only
      job_queries.py            Reusable WHERE / ORDER fragments (tabs, search, sort)
      job_service.py            Use cases: add manual job, hide/unhide, list a tab
      job_mapper.py             Entity/row -> view model or JSON dict
      job_view.py               View-model / response dataclasses (the "DTOs")
      job_routes.py             Flask Blueprint: HTTP only, thin
    prefilter/                  Free (no-LLM) filtering rules
    scoring/                    Claude scoring, batch submit/collect, schemas
    applications/               Drafts, sending, status board, update checks
    alerts/                     Alert-email parsing into jobs
    cv/                         CV upload, text extraction, analysis
    preferences/                profile.yaml + .env settings
    usage/                      Token/cost tracking and the AI-spend page

  sources/                      Job-feed adapters (Open/Closed: add a file, not an `if`)
    job_source.py               `JobSource` Protocol: name, fetch(profile) -> list[Job]
    remotive_source.py          One class per feed
    ...
    source_registry.py          The list of enabled sources

  pipeline/                     Orchestration only: task runner, scheduler, step order
                                (calls services and has no business rules of its own)

  lib/                          Third-party / infrastructure wrappers (never import domain/)
    database.py                 Connection, schema, column migrations
    llm_client.py               Anthropic client, cost calc, usage logging hook
    mail_client.py              IMAP / SMTP
    http_client.py              httpx client + browser headers

  shared/
    utils/                      Pure helpers: text_utils.py, money_utils.py, date_utils.py
    constants/                  work_types.py, application_statuses.py, ...

  templates/                    Atomic Design (see UI section)
    components/atoms/  components/molecules/  components/organisms/
    layouts/                    base.html (the "templates" tier)
    pages/                      one per route: jobs.html, job.html, ...
  static/
    css/                        tokens.css, then one file per component tier
    js/                         ES modules (see UI section)

tests/                          pytest, mirrors jobradar/ (tests/domain/jobs/test_job_service.py)
```

### Structure Rules

* Group by **feature domain**, not by technical type. A feature's entity, repository, service, mapper, views and routes live together in `domain/<feature>/`.
* File names say what the file is: `<feature>_<role>.py` (`job_repository.py`, not `repo.py`). Python modules are `snake_case`.
* Keep each file **under ~200 lines**. When a file grows past that, split it by responsibility. Don't just move lines around.
* Documentation goes in `README.md` or `docs/`, never in `shared/utils`.

---

# Migration Policy (the codebase isn't there yet)

The current code is flat (`jobradar/web.py`, `scorer.py`, `sources.py`, ...). **Don't big-bang refactor.**

* **New code** goes straight into the target structure.
* **When you change existing code**, move the part you touch into its target home in the same change: extract the SQL into a repository, the rule into the entity/service, the route into a blueprint. Leave a re-export in the old module only if other callers still import it.
* A refactor-only change must not change behaviour. Keep it in its own commit.
* Moving the whole of a large module (e.g. splitting `web.py` into blueprints) is fine **when the user asks for it**.

Known hotspots to fix as you touch them:

| Where | Problem | Target |
|---|---|---|
| `web.py` (676 lines) | Routes build SQL, call `scorer._save`, parse JSON | `domain/*/…_routes.py` → services |
| `sources.py` `Fetcher` (444 lines) | Every feed in one class | `sources/*_source.py` + registry |
| `templates/_ui.html` `job_card` | `loads(analysis)`, pay-string fallback logic | `job_mapper.py` builds a `JobCardView` |
| `db.DB` | One class for every table | `lib/database.py` + one repository per table |

---

# Layered Architecture

```text
[HTTP request / CLI / scheduler]
        ↓
[Route or run.py]  →  [Service]  →  [Repository]  →  [lib/database]
                         │  uses Entities (rules) and Mappers (output shape)
                         └→ [lib clients: llm_client, mail_client, http_client]
        ↑
[View models / response dicts returned to the caller]
```

| Layer | Does | Never does |
|---|---|---|
| **Route** (`*_routes.py`) | Parse request, call **one** service method, render/`reply()` | SQL, business rules, LLM calls, `json.loads` of stored data |
| **Service** (`*_service.py`) | Use cases, transactions, calls repos + lib clients, returns view models | Import `flask`, `request`, `g`, render templates |
| **Entity** (`<feature>.py`) | State + rules (`application.advance_to(status)` refuses to go backwards) | SQL, HTTP, I/O |
| **Repository** (`*_repository.py`) | SQL for its own table(s), row ↔ entity | Business rules, calls to other repositories' tables |
| **Queries** (`*_queries.py`) | Reusable SQL fragments with bound params | String-formatting user input into SQL |
| **Mapper** (`*_mapper.py`) | Entity → view model / JSON dict | I/O |
| **lib/** | Wrap SQLite, Anthropic, IMAP/SMTP, httpx | Import from `domain/` |
| **shared/utils** | Pure functions (formatting, parsing, money) | I/O, state |

Dependency direction is **inward only**: routes → services → (entities, repositories, lib). `lib/` and `shared/` depend on nothing in `domain/`.

---

# SOLID (applied here)

* **SRP:** one reason to change per class/module. A service that both scores jobs and sends emails is two services.
* **OCP:** extend by adding, not editing. New job feed = new `*_source.py` + one registry line. New work type or status = a constant, not a new `elif` chain scattered around.
* **LSP:** every `JobSource` returns `list[Job]` and raises the same error type. Callers never special-case a source.
* **ISP:** small `Protocol`s (`JobSource`, `MailSender`, `LlmClient`). Don't make a class implement methods it doesn't use.
* **DIP:** services take their dependencies in `__init__` (repositories, `llm_client`, `mail_client`). They never construct them or reach for globals. `container.py` wires everything, and tests pass fakes.

```python
# ❌ Bad: route does SQL + rules + LLM
@app.post("/jobs/<path:job_id>/score")
def job_score(job_id):
    msg = llm.create(scorer.request_params(db().job(job_id), ...))
    scorer._save(db(), job_id, scorer.parse(msg))

# ✅ Good: route is thin, service owns the use case
@jobs_bp.post("/<path:job_id>/score")
def score(job_id: str):
    result = container.scoring_service().score_one(job_id)
    return reply(True, result.message, **asdict(result))
```

```python
# ✅ Entity owns the rule
@dataclass
class Application:
    status: str

    def advance_to(self, new_status: str) -> bool:
        """Auto-updates only move forward along the board."""
        if STATUS_ORDER.index(new_status) <= STATUS_ORDER.index(self.status):
            return False
        self.status = new_status
        return True
```

---

# Clean Code

* Meaningful names; no single-letter names except loop indices and comprehensions. Existing terse names (`d`, `j`, `a`) get renamed when you touch them.
* Small functions that do one thing. Type hints on every public function.
* `@dataclass` for entities and view models; `Protocol` for abstractions; `Enum`/constants instead of magic strings.
* Docstrings only where the *why* isn't obvious (match the existing sparse style). No comments restating code.
* Raise domain errors (`ScoringError`, `MailError`, `LLMError`) from services. Routes turn them into user-friendly messages that suggest a next step.
* Double quotes in Python. 4-space indent. Keep lines readable (~120 max).
* Parameterised SQL only (`?` placeholders). Never f-string user input into SQL.

---

# UI: Atomic Design (Jinja + CSS + vanilla JS)

| Tier | Location | Examples (from today's UI) |
|---|---|---|
| **Atoms** | `templates/components/atoms/*.html` | `icon`, `button`, `chip`, `badge`, `ring` (score) |
| **Molecules** | `templates/components/molecules/*.html` | `work_chip`, `fit_chip`, `search_box`, `stat_tile`, `empty_state` |
| **Organisms** | `templates/components/organisms/*.html` | `job_card`, `apply_panel`, `board_column`, `task_progress`, `prefs_section` |
| **Templates** | `templates/layouts/*.html` | `base.html` (sidebar, header, toasts) |
| **Pages** | `templates/pages/*.html` | `jobs.html`, `job.html`, `applications.html`, `cv.html`, ... |

### Rules

* One macro file per component, named after the component: `atoms/chip.html` exposes `chip(...)`.
* A tier may only import **lower** tiers (organisms import molecules/atoms, never pages).
* Templates **render only**: no `loads(...)`, no fallback chains that compute values, no business decisions. The service/mapper passes a ready view model (`JobCardView.pay_label`, `.matched_skills`, `.applied_badge`).
* Pages extend a layout and compose organisms; they hold no reusable markup.
* **CSS:** design tokens (colors, spacing, radii) in `static/css/tokens.css` as custom properties. One file per tier (`atoms.css`, `molecules.css`, `organisms.css`, `layout.css`). Class names match the component (`.job-card`, `.chip`). No inline styles except CSS variables like `--p`.
* **JS:** ES modules loaded with `<script type="module">`, no bundler.
  * `static/js/lib/http.js` holds `post()`. `static/js/lib/dom.js` holds `$`, `$$`, `esc`.
  * `static/js/components/<component>.js` holds the behaviour for one organism/molecule (`toast.js`, `job-card.js`, `board.js`).
  * `static/js/pages/<page>.js` wires components for one page.
  * Components bind via `data-*` attributes (as today: `data-act`, `data-task`). No inline `onclick`.
  * Always escape interpolated HTML with `esc()`.

---

# Product Invariants (do not break)

These keep the app cheap and safe, so treat them as requirements:

1. **A job is scored at most once, ever.** Duplicates (same fingerprint) never reach the LLM.
2. **The prefilter is free.** No LLM or network calls in `domain/prefilter/`.
3. **Every Claude call goes through `lib/llm_client`** and logs usage with a `purpose` (`score`, `alert`, `cv`, `draft`, `classify`, ...).
4. **Each email is sent to Claude at most once** (`emails_seen`).
5. **Application statuses only move forward automatically.** The user can move them any direction.
6. **Nothing is sent or submitted without an explicit user click.** No auto-apply on job sites.
7. **Secrets live only in `.env`**, are never logged, never sent to Claude, and never committed. `profile.yaml`, `jobs.db` and `data/` stay gitignored.
8. **The web server binds to `127.0.0.1` only.** Keep the same-origin check on POSTs.
9. Schema changes are **additive** (new columns via the migrations map in `lib/database.py`). Never drop or rename a column that holds user data.

---

# Reuse Before Creating New

Before adding a helper, constant, macro, JS function or service method, search for an existing one (`shared/utils`, `shared/constants`, `components/`, `static/js/lib`) and extend it. Follow the pattern already dominant in the module you're editing rather than introducing a parallel mechanism.

---

# Testing

* `pytest`, files named `test_*.py` under `tests/`, mirroring `jobradar/`.
* Unit-test entities, services (with fake repositories/clients via DIP), mappers, prefilter rules and source parsers (saved fixture payloads, no live HTTP).
* Never call the real Anthropic API, IMAP or SMTP in tests.
* Add `pytest` to a `requirements-dev.txt` when the first test lands.

---

# Git

* Branch prefixes: `feat/`, `fix/`, `chore/`, `refactor/` + a short kebab-case slug (`feat/jobstreet-source`).
* Conventional commits (`feat(scoring): cache profile prompt`). **Atomic commits:** one logical change each, and keep refactors separate from behaviour changes.
* Never commit `.env`, `profile.yaml`, `jobs.db`, `data/`, `.venv/`.
* Never rename a branch that has an open PR (GitHub closes the PR).

---

# AI Behaviour Requirements

When generating code, always:

1. Put code in its target location per the structure above (and migrate what you touch)
2. Keep routes and `run.py` thin; business logic in services and entities
3. Keep SQL in repositories; keep third-party calls in `lib/`
4. Inject dependencies; don't construct them inside services
5. Return view models from services; keep templates render-only
6. Build UI from atoms → molecules → organisms → layouts → pages
7. Keep files small and single-purpose (SRP)
8. Respect every Product Invariant
9. Reuse before creating new
10. Ask before doing anything that conflicts with these rules
