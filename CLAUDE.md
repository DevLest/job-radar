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

# Directory Structure

```text
run.py                          CLI entry point -> jobradar/cli/main.py
jobradar/
  app.py                        Flask app factory (blueprints, filters, guards) + serve()
  container.py                  Composition root: one Container per request / background task (DIP)
  cli/                          main.py (argparse, pipeline commands), commands.py (stats, report, dry-run)

  domain/                       One folder per feature - never grouped by technical type
    jobs/
      job_posting.py            JobPosting: a job as a source reports it
      job.py                    Job entity: funnel state + rules (hide(), queue(), record_score())
      job_repository.py         SQL for the `jobs` table only (row <-> Job)
      job_queries.py            Reusable WHERE / ORDER fragments + JobListFilter
      job_service.py            Use cases: list a tab, detail page, add a manual job, hide/unhide
      job_mapper.py             Job -> JobCardView / JobDetailView
      job_prompt_mapper.py      Job -> the plain text Claude sees
      job_labels.py             Words for Claude's enum answers, meter percentages
      job_view.py               View-model dataclasses (the "DTOs")
      job_routes.py             Blueprint "jobs": HTTP only, thin
    applications/               entity, repositories, lifecycle/draft/sending services,
                                reply / posting / follow-up checks, board mapper + views, routes
    prefilter/                  prefilter_rules.py (RULES list), text_signals.py, pay_conversion.py, service
    scoring/                    scoring_prompt.py, scoring_service.py (real-time), batch_scoring_service.py,
                                batch_repository.py, cost_estimator.py
    alerts/                     alert_links.py, alert_extractor.py (Claude), alert_service.py, seen_email_repository.py
    cv/                         cv_files.py, cv_prompt.py, cv_repository.py, cv_profile_merge.py, cv_service.py, routes
    preferences/                profile.yaml: defaults, repository, field definitions, form codec, service, routes
    settings/                   .env connections: settings_service.py, routes
    usage/                      token/cost repository, AI-spend page service, routes
    home/                       home_service.py (dashboard), layout_service.py (sidebar counts), routes
    report/                     static HTML/CSV report builder

  sources/                      Job-feed adapters (Open/Closed: add a file + one registry line)
    job_source.py               JobSource / CompanyBoardSource Protocols + SourceQuery
    <name>_source.py            One class per feed or ATS board
    source_parsing.py           Salary, work type, number parsing shared by sources
    source_registry.py          FEED_SOURCES / BOARD_SOURCES, in run order
    feed_collector.py           Runs every enabled source; one broken source never stops a run

  pipeline/                     Orchestration only: pipeline_steps.py, task_runner.py, scheduler.py,
                                task_routes.py (no business rules of their own)

  lib/                          Infrastructure wrappers (never import domain/)
    database.py + database_schema.py   Connection, schema, additive column migrations
    key_value_store.py          The meta table
    llm_client.py               Anthropic calls, batches, cost, usage callback
    mail_client.py + email_text.py     IMAP / SMTP, email -> compact text
    http_client.py              httpx client + browser headers
    env_file.py                 .env load / write

  shared/
    constants/                  paths.py, work_types.py
    utils/                      date_utils.py, text_utils.py, format_utils.py, dict_utils.py, hash_utils.py

  web/                          Flask plumbing: request_scope.py (container per request), responses.py
                                (reply / JSON), security.py (same-origin POSTs), template_helpers.py, icons.py

  templates/                    Atomic Design (see UI section)
    components/atoms/  components/molecules/  components/organisms/
    layouts/base.html           the "templates" tier
    pages/                      one per route: home, jobs, job, applications, application, cv, preferences, settings, usage
  static/
    css/                        tokens.css, base, layout, atoms, job-list, forms, pages, organisms, misc (link order = cascade)
    js/                         main.js + lib/ + components/ + pages/ (ES modules, no bundler)

tests/                          pytest, mirrors jobradar/ (tests/domain/jobs/test_job_service.py)
```

### Structure Rules

* Group by **feature domain**, not by technical type. A feature's entity, repository, service, mapper, views and routes live together in `domain/<feature>/`.
* File names say what the file is: `<feature>_<role>.py` (`job_repository.py`, not `repo.py`). Python modules are `snake_case`.
* Keep each file **under ~200 lines**. When a file grows past that, split it by responsibility. Don't just move lines around.
* Documentation goes in `README.md` or `docs/`, never in `shared/utils`.

---

# Keeping the Structure

The app was rebuilt into this structure with no behaviour change, checked page by page, prompt by prompt and
database row by row against the original. Keep it that way:

* Every change lands in its feature folder. If you need a new place, add it here first.
* A refactor-only change must not change behaviour. Keep it in its own commit, separate from features.
* When a file approaches ~200 lines, split it by responsibility before adding more.
* `container.py` is the only place that constructs services. Anything new gets a `cached_property` there.

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
* **LSP:** every `JobSource` returns `list[JobPosting]` and raises the same error type. Callers never special-case a source.
* **ISP:** small `Protocol`s (`JobSource`, `CompanyBoardSource`; clients injected via `container.py`). Don't make a class implement methods it doesn't use.
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
| **Atoms** | `templates/components/atoms/*.html` (+ CSS-only atoms like `.btn`) | `icon` (global), `chip`, `badge`, `ring`, `verdict_word`, `stat_icon` |
| **Molecules** | `templates/components/molecules/*.html` | `work_chip`, `stat_tile`, `empty_state`, `mini_job`, `timeline_item`, `pref_field`, form fields |
| **Organisms** | `templates/components/organisms/*.html` | `job_card`, `job_hero`, `score_breakdown`, `apply_panel`, `board`, `status_track`, `sidebar`, `find_dialog`, `task_progress`, `pref_section`, `cv_profile` |
| **Templates** | `templates/layouts/*.html` | `base.html` (sidebar, header, toasts) |
| **Pages** | `templates/pages/*.html` | `jobs.html`, `job.html`, `applications.html`, `cv.html`, ... |

### Rules

* One macro file per component, named after the component: `atoms/chip.html` exposes `chip(...)`.
* A tier may only import **lower** tiers (organisms import molecules/atoms, never pages).
* Templates **render only**: no `loads(...)`, no fallback chains that compute values, no business decisions. The service/mapper passes a ready view model (`JobCardView.pay_short`, `.matched_skills`, `.applied_badge`).
* Pages extend a layout and compose organisms; they hold no reusable markup.
* **CSS:** design tokens (colors, spacing, radii) in `static/css/tokens.css` as custom properties. The files are listed in `web/template_helpers.py` `STYLESHEETS`; that link order is the cascade, so add rules to the file whose section they belong to rather than reordering. Class names match the component (`.job-card`, `.chip`). Prefer classes over adding new inline styles.
* **JS:** ES modules loaded with `<script type="module">`, no bundler.
  * `static/js/lib/http.js` holds `post()`. `static/js/lib/dom.js` holds `$`, `$$`, `esc`.
  * `static/js/components/<component>.js` holds the behaviour for one organism/molecule (`toast.js`, `job-card.js`, `board.js`).
  * `static/js/pages/<page>.js` wires components for one page.
  * Components bind via `data-*` attributes (`data-act`, `data-task`, `data-open-dialog="#id"`, `data-autosubmit`, `data-reload`, `data-set-status`). No inline `onclick` / `onchange`.
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

1. Put code in its feature folder per the structure above
2. Keep routes and `run.py` thin; business logic in services and entities
3. Keep SQL in repositories; keep third-party calls in `lib/`
4. Inject dependencies; don't construct them inside services
5. Return view models from services; keep templates render-only
6. Build UI from atoms → molecules → organisms → layouts → pages
7. Keep files small and single-purpose (SRP)
8. Respect every Product Invariant
9. Reuse before creating new
10. Ask before doing anything that conflicts with these rules
