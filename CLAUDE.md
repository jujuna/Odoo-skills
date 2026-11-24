# Odoo 19 Project — Organization Instructions

Portable instructions for developers, testers, consultants, and managers working on Odoo 19 modules. Do not hardcode machine usernames, personal database names, or local paths in skills, hooks, or scripts — discover them from the active workspace.

## Workspace Modes (Auto-Detect First)

| Mode | What is present | How to behave |
|---|---|---|
| **Full Workspace** (Developers / QA) | `odoo/`, `addons/`, `enterprise/`, `custom_addons/`, optional `odoo.conf`, venv, PostgreSQL, `documentations/` | Read `odoo.conf` if present; otherwise Odoo 19 uses PostgreSQL 14 on default port `5432` with explicit `--addons-path`. Verify behavior against source and (when requested/available) read-only `psql SELECT` or scratch tests. |
| **Light Workspace** (Managers / Consultants) | Only 2–3 Odoo source module folders + custom modules (no `odoo-bin`, no `odoo.conf`, no DB, no venv, no `documentations/`) | Work directly from the folders present. Never crash on missing folders or DB tools. Mark anything outside available source/DB as `not verified — not present in this workspace`. |

## Directory Ownership (When Present)

| Directory | Role |
|---|---|
| `odoo/`, `addons/`, `enterprise/` | Odoo 19 core — **read-only, never modify** |
| `custom_addons/gec_odoo_modules/` | **Main shared custom module repository (branch `19.0`).** All core custom logic lives here. |
| Other `custom_addons/*/` folders | Separate client/project repositories (20+ project folders exist). **Never copy files between folders and never edit another project folder unless the user explicitly names it.** |
| `documentations/` | Module and business-flow documentation only (index in `documentations/INDEX.md`) |
| `outputs/` | Generated deliverables such as manual test checklists (`.xlsx` + `.json` spec) |
| `.claude/skills/` | Source of truth for Odoo 19 skills (`.agents/skills/` symlinks here for cross-tool discovery) |
| `.claude/agents/` & `.claude/hooks/` | Subagent role briefs (7 roles, mirrored natively in `.agents/plugins/odoo-agents/`) and deterministic safety/offline-check hooks |

## Odoo 19 Version & Environment Discovery

- **Target:** **Odoo 19.0 FINAL**, Python 3.10–3.14 (avoid PEP 695 3.12-only type syntax), PostgreSQL 13+ (local Odoo 19 uses PG 14 on port `5432`).
- **Python binary:** Prefer the workspace venv (`data_venv/bin/python`, `.venv/bin/python`, or `venv/bin/python`) when present so syntax checks and packages (`lxml`, `openpyxl`, `polib`, optional `ruff`) match the Odoo 19 runtime; fall back to `python3` in Light Workspaces.
- **Search trap (`.git/info/exclude`):** In a full checkout, `.git/info/exclude` hides `custom_addons/`, `enterprise/`, `documentations/`, `themes/`, `*.md`, and `.port19_wt/`. Always search explicit folders (`custom_addons/gec_odoo_modules/`, `addons/`, `enterprise/`, `documentations/`), never `.` or the repo root. Never blindly search all of `custom_addons/` where 20+ separate project folders hold duplicate module copies.

Non-negotiable Odoo 19 boundaries (full rules in `.claude/skills/odoo-dev/references/guardrails.md`, v20-only blockers in `scripts/v20_patterns.txt`):
- **Security:** `security/ir.model.access.csv` (8 columns) **plus** XML `ir.rule` records — **never** use Odoo 20's `ir.access` or `('field', 'access', 'read')`. Groups use `user_ids` and `privilege_id`.
- **OWL 2:** `useState()`, `useRef()`, `static props`, `useEffect()`, `t-slot`, `t-ref="name"` — **never** use Odoo 20 OWL 3 `proxy()`, `signal.ref()`, `useProps()`, `useListener()`, `useLayoutEffect()`, or `t-call-slot`.
- **No `compute_sql=`** and **no `ir.config_parameter.get_str()`** — both are Odoo 20-only. Use `search=` / `store=True` and `get_param()`.
- **Constraints & Views:** `_sql_constraints` is ignored in Odoo 19 — use `models.Constraint` / `models.UniqueIndex`; `<tree>`, `attrs=`, `states=`, `numbercall`, `_name_search`, and `groups_id` on `ir.actions.*` are removed/invalid; Font Awesome (`fa fa-*`) is still used (no Material Symbols `data-icon=`).

## Standing Rules

- **Zero hallucination — proof before every claim or action.** Every factual claim needs a verified source `path:line` (with quote when handing off), a read-only `psql SELECT`, or a test run in this session. Otherwise say `not verified — assumption` and do not act on it.
- **Multi-company by default.** Every model storing business data gets `company_id`, `check_company=True` on scoped relations, `_check_company_auto = True`, and a global multi-company `ir.rule` in XML. Single-company needs a stated reason.
- **Sweep before changing existing code.** Check callers, overrides, inheriting views, `@api.depends`, and cross-module readers (`coupling-map.md`), and report the result.
- **Match core.** Find the pattern in `addons/` / `enterprise/` and follow it.
- **Never copy across project folders.** Keep changes strictly inside `gec_odoo_modules/` unless the user explicitly asks to edit another project folder.
- **Ask before writing tests or in-module docs.** Say what you would cover and let the user decide.
- **Main session decides; agents read.** Delegate wide/parallel reading (>3 files or >300 lines) to `odoo-scout` / `odoo-tracer` agents. Settle small lookups directly.
- **Untouched code below standard (Hard Rule 15):** never silently refactor or edit untouched code outside the task; report it separately as a proposal and let the user decide.

## Safety (Enforced by `.claude/hooks/odoo_safety_guard.py`)

- Never edit `odoo/`, `addons/`, or `enterprise/`.
- Never drop a database, delete or re-init a PostgreSQL data directory, or run `pg_upgrade` / `initdb`. Only exception: disposable scratch test databases (`gec19_t_*` / `odoo_t_*`) created and dropped at the user's request.
- Never set `PGPORT` globally, never edit `~/.odoorc`, and never run `odoo-bin` with `-s` / `--save`.
- Never write to a working or production database unless the user explicitly names it and asks. Never send test payments or batches to live bank or external government/signing endpoints.
- Read-only `psql SELECT` queries on the workspace port (default `5432`, or `odoo.conf` port) are pre-approved.

## Communication & Coding Conventions

- Plain, short, direct answers — no filler, no emojis. Lead with purpose, one concrete example with numbers (where relevant), and the direct answer.
- Clickable markdown links for code citations: `[file.py:42](path/file.py#L42)`.
- Never modify docstrings, comments, or formatting on lines outside your change.
- Optional `ruff`: when `ruff` is installed, run it for correctness, security, and imports while preserving the team's `compact-code.md` layout.

## Documentation Rule (When `documentations/` Exists)

When Odoo business logic comes up in a full workspace with `documentations/`:
1. Check `documentations/<module>.md` first and answer from it if current.
2. If missing or incomplete and appropriate for a dev session, research from source, document using `.claude/skills/odoo-dev/references/doc-template.md`, and update `documentations/INDEX.md` (all links use `../` prefix).
3. In consulting-only sessions (`odoo-consultant`) or Light Workspaces without `documentations/`, do not create or edit `documentations/` unless the user asks.
