---
name: odoo-dev
description: >
  Use this skill for Odoo 19 development tasks: create, modify, review, debug, refactor, secure,
  optimize, or migrate modules and code (models, views, controllers, wizards, reports, manifests,
  ACLs/record rules, multi-company, cron, QWeb, OWL 2, ORM/SQL, integrations). Trigger on
  Odoo-specific terms like __manifest__.py, ir.model.access, ir.rule, record rules, model/view
  inheritance, jsonrpc/JSON-2 API, performance, security, multi-company, and
  customization requests. Also triggers for code quality reviews and "make my code better /
  shorter / cleaner without changing logic", Odoo business module learning, documentation
  requests (module READMEs: odoo-readme), and "how does X work in Odoo" when the answer lives
  in the code. Client discovery, configuration choices and teaching consultants belong to
  odoo-consultant.
---

# Odoo 19 Development Skill

Produce production-grade Odoo 19 code. Keep this file compact — load references on demand.

**This repo is Odoo 19.** Odoo 20 replaced the security system, the OWL version and several ORM
signatures. If you are about to write something you remember from v20 (`ir.access`,
`compute_sql`, OWL 3 `proxy()`), check the v20-only list in `references/guardrails.md` first.

---

## Hard Rules — always active

Easy, clean, short, correct. Rule N is explained, with examples, in section N of
`references/simplicity.md`.

1. **Say what the request misses.** Before planning, check the request itself: does core or
   a setting already do it, which flows and modules does it touch that nobody named, which
   cases does it leave out (other companies, cancel / reset / refund, existing records,
   another currency, import, cron, portal)? Put what matters first in the answer, with the
   simpler way if there is one.
2. **Smallest change wins.** Take the highest option that works: configuration → a field or
   view attribute (`related`, `compute`, `default`, `domain`, `readonly`) → extend an
   existing method through its core hook with `super()` → a new field or method → a new model
   → a new module. Each step down needs a stated reason.
3. **No over-engineering.** Solve the case in front of you. No helper for one caller, no
   wrapper, no abstraction, hook, option or setting "for later", no override where a field
   attribute or a core hook does the job.
4. **Find the connections.** Before changing anything that exists, find what reaches it and
   what it reaches: callers, overrides, inheriting views, `@api.depends` and `related`
   chains, reports, other modules that read the same data, code stored in the database
   (`scripts/db_refs.sql`), and what existing records get at upgrade. The result goes in the
   answer. No sweep → no change. `references/dependencies.md`, `references/coupling-map.md`.
5. **Respect core logic.** Copy the pattern from `addons/` or `enterprise/`. `super()` on
   the normal path; never re-implement or "correct" a core method, never hide or replace a
   core screen element: when core misleads on our data, add our element beside it. Never
   re-compute or net an amount Odoo already computes. Clever or unusual = wrong.
6. **Reuse, never duplicate.** Before writing a method, field or helper, search the module,
   its `depends` and core for one that does the job. Logic needed twice lives once, in the
   module both depend on. No second field holding the same data (`related=`), no second
   model or screen for one business action.
7. **No fixed business values in code.** Rates, amounts, limits, dates, accounts, taxes,
   journals, partners, products and groups come from the record that owns them: a field, an
   xmlid, a company setting, a rule parameter, a `noupdate` data record. A literal only for
   what changes together with the code (state values, field names, an external API's element
   names), named once.
8. **No validation nobody asked for.** Make the bad value impossible instead (domain,
   readonly, default). A new `raise`, constraint, `required=True` or guard the task did not
   ask for is a proposal: name the bad case it blocks in one line and let the user decide.
9. **Proof, not guessing.** Every claim needs a source file+line, a `psql SELECT`, or a test
   run. Otherwise say "not verified — assumption". Never invent a field, method or option.
10. **Multi-company and access by default.** Every model that stores business data gets
    `company_id`, `check_company=True` on scoped relations and a multi-company `ir.rule`;
    every new model gets `security/ir.model.access.csv` rows (groups file first in the
    manifest, then `ir.model.access.csv`, then rules). Single-company needs a stated reason.
    `references/multicompany.md`.
11. **Compact code: one line, few docstrings, no comments.** A statement that fits in 120
    characters stays on one line; over that, shorten the code before splitting it. No module
    or `_inherit` class docstrings. A method gets a docstring only when it says what the name
    and body cannot (the why, a business rule, a gotcha): one line, three at most. Inline
    comments only for one genuinely non-obvious line; user errors one sentence. No guards for
    what is always there, no `except Exception` outside a cron's per-record loop. Never touch
    lines you did not change. `references/compact-code.md`, `references/ai-smells.md`.
12. **Ask before tests; never migrations or version bumps.** Tests, and READMEs or docs
    inside a module, only after the user says yes (say which behaviors you would cover).
    Never a migration script. Never bump `version` in `__manifest__.py`; flag a prefix other
    than `19.0.` (uninstallable on 19) and change it to `19.0.` only with the user's OK.
13. **Plain on screen & Georgian UI strings.** Every label, help text, button, message, and
    error uses plain business words (never field names or Odoo jargon). Errors say what
    happened and what to do next in one sentence. Keep `i18n/ka_GE.po` synced whenever
    user-visible text changes.
14. **Readable and easy to change.** Clear names, one job per method (~40 lines max per
    helper), normal path top to bottom, each rule in one place. When packing hurts
    readability, keep it readable.
15. **Existing code below our standard.** Never silently refactor untouched code outside
    your change; list concrete Hard Rule violations seen in opened files separately as
    proposals and let the user decide.

---

## Reference Router

Load **only** the file(s) the current task needs.

### Always, for any code change
| File | Why |
|---|---|
| `references/simplicity.md` | the 12 Hard Rules in detail, with examples — outranks every other file |
| `references/dependencies.md` | impact sweep (Tiers 1-4) + precedent search before touching anything |
| `references/coupling-map.md` | which of our modules produce, read and configure each business object |
| `references/guardrails.md` | v19 API forms, banned patterns, v20-only APIs never to use |
| `references/compact-code.md` | line length and splitting, imports, docstrings, comments, messages |
| `references/ai-smells.md` | guards, fallbacks, swallowed errors and helpers to cut; the core-first check |

### v19 specifics
| Task | File |
|---|---|
| unsure whether an API exists in 19, or is v20-only | `references/guardrails.md` |
| ACLs, record rules, sudo, portal, IDOR | `references/security.md` |
| company scoping, `check_company`, branches, `with_company` | `references/multicompany.md` |

### By area
| Task | File |
|---|---|
| ORM correctness, recordsets, overrides, domains | `references/orm.md` |
| N+1 fixes, batching, cache, profiling | `references/performance.md` |
| Python style, logging, errors, inheritance, ormcache | `references/python.md` |
| Commit safety, savepoints, rollback, cache after SQL | `references/transactions.md` |
| Field types, compute, inverse, constraints | `references/fields.md` |
| Raw SQL, indexes, query plans | `references/sql.md` |
| Full module skeleton / boilerplate | `references/scaffold.md` |
| OWL 2 components, services, hooks | `references/owl.md` |
| XML views, inheritance, expressions, QWeb reports, icons | `references/views.md` |
| HTTP/JSON-RPC controllers, JSON-2 API, portal | `references/controllers.md` |
| Wizards (TransientModel), multi-step, actions | `references/wizards.md` |
| mail.thread, tracking, message_post, activities | `references/mail.md` |
| Scheduled actions, batch jobs, progress | `references/cron.md` |
| XML/CSV data files, noupdate, manifest order | `references/data-files.md` |
| Unit/integration tests, Form simulation | `references/testing.md` |
| Business module learning / documentation | `references/doc-template.md` |
| Code quality review, "make it better / shorter / organized", refactor without behavior change | `references/refactor.md` + `ai-smells.md` + `compact-code.md` |
| Pre-output quality check | `references/checklist.md` |

Proof & mechanical scripts live in `scripts/`:
- `sweep.py` (dependency sweep), `map_rows.py` (coupling-map lookup), `db_refs.sql` (DB-stored code/domains), `doc_link_check.py` (verify `documentations/*.md` source links), `v20_patterns.txt` (Odoo 20-only blockers).
- Refactor proof toolkit (`references/refactor.md` §9): `code_inventory.py`, `dead_names.py`, `split_check.py`, `oldnew.py`, `odoo_import_check.py`, `compact_scan.py`.

**Auto-load rules**
- Any code change → `simplicity.md` + `dependencies.md` + `guardrails.md` + `compact-code.md`
  + `ai-smells.md`
- A change to taxes, accounts, contacts, journals, payments, payslips, states or declarations →
  `coupling-map.md` + `dependencies.md` Tier 4, and the docs of every module it lists
- New model or field storing business data → `multicompany.md`
- Any security file → `security.md`
- Full module request → `scaffold.md`
- Fields / compute / onchange → `fields.md`
- Non-trivial ORM code → `orm.md`; performance-sensitive → `+ performance.md`
- Frontend → `owl.md`
- Tests (after the user says yes) → `testing.md`
- Quality review or refactor of existing code → `refactor.md` + `dependencies.md`, and
  `scripts/compact_scan.py <module>` for the `compact-code.md` / `ai-smells.md` candidates

---

## Execution Workflow

1. **Classify:** `build` | `fix` | `review` | `refactor` | `security` | `performance` |
   `migration` | `frontend` | `learn/document`
2. **`learn/document`** → Documentation Workflow below
   **`review` / `refactor`** → `refactor.md`: measure first, plan per phase, the user approves
   each phase and commits it; bugs found are listed, never fixed inside the refactor
3. **Code tasks** → load `simplicity.md` + `dependencies.md` + `guardrails.md` + the
   matching area file(s)
4. **Check the request** (rule 1): what core or a setting already does, the flows and cases
   it leaves out.
5. **Sweep** (rules 4-6): the connections in both directions, the core precedent, and the
   existing code to reuse. State the result in the answer.
6. **Write** the minimal correct code for the request scope: business values read from their
   records, no validation nobody asked for, multi-company aware, with its
   `ir.model.access.csv` rows and rules if it introduces a model.
7. **Check** against `references/checklist.md` before returning.
8. **Tests** — ask, do not assume.

---

## Explaining to the User

- Plain, simple English. Short. No jargon beyond the Odoo terms they already use.
- Lead with the one-sentence answer, then the proof: a source line, a real example, numbers.
- Concrete beats abstract ("invoice 123 posts 100 GEL to 3120" beats "the payment logic
  reconciles the counterpart").
- As short as the answer allows, with a snippet or a small table where it carries the proof.
  No walls of text, no restating the question, no listing what you did not check.
- If the honest answer is "not verified", say it in the first line.
- What the request misses (rule 1) comes before the answer. What the user must decide (a
  validation, a new setting or model, a behavior change) goes last under **Your call**, one
  line each: the choice, the risk, your recommendation.

---

## Using Subagents

**Main session decides; agents read, write, and verify.** Delegate wide/parallel reading (>3 files or >300 lines) to read-only agents (`odoo-explore`, `odoo-scout`, `odoo-tracer`). Keep small lookups (<= 3 files) direct. Full choreography lives in `odoo-team` (and `.agents/skills/odoo-agents/SKILL.md` for Antigravity).

| Agent | Model | Use for |
|---|---|---|
| `odoo-explore` | Haiku | Fast file/symbol discovery across explicit repo folders |
| `odoo-scout` | Haiku | Wide/mechanical reading: sweeps (`sweep.py`), fact extraction, core precedents, reuse search, checklists, Clean checks (up to 5 in parallel) |
| `odoo-tracer` | Sonnet | Flow sweeps of a business object (`map_rows.py`, Tier 4) and end-to-end `super()` / OWL 2 RPC traces |
| `odoo-builder` | Sonnet | Implementing an approved single-module plan + running Odoo 19 offline checks |
| `odoo-bug-hunter` | Opus | Critical plans: core-flow, security, and cross-module collisions with `path:line` proof |
| `odoo-reviewer` | Opus | Critical or multi-file changes: independent diff review (Odoo 19, security, OWL 2, simplicity, Hard Rules 1–15) |
| `odoo-verifier` | Sonnet | Adversarial code-first verification of blockers/claims + existing tests on a user-named test DB |

**Critical** = touches security (`ir.model.access.csv`, `ir.rule`, `sudo()`, controllers/public RPC), money/taxes/declarations/postings/bank, multi-company boundaries, core method overrides or required/constrained fields on core models, states, stock valuation, or payroll flows.

**Map the impact before you design.** Name the business objects the task touches (taxes,
accounts, contacts and their flags, journals, states, posted entries, payslips, declarations,
bank requests). For each: its rows in `references/coupling-map.md`, the
`documentations/<module>.md` of every module listed there, and one scout per object for the
flow sweep (`references/dependencies.md`, Tier 4). Our own docs come before any design: their
Design Decisions and Gotchas hold the rules a redesign breaks. No impact map, no plan for money,
payroll, taxes or declarations.

**Delegate reading by default.** Split the work into one-task scout prompts and run them in
parallel (up to 5 scouts at a time, queue the rest). Read yourself only:
- the lines a decision rests on, opened from a scout's path:line to check it
- a one-line answer from a single `grep` or `SELECT`

**Loop until nothing is open.** Read every scout result, open the lines your decision rests
on, then decide or send the next batch of scouts for what is still unclear. Many small checks
beat one big one: split by file, by question or by check.

**A code change:**
1. Scouts collect: the impact map (coupling map rows, docs of the modules in scope, a flow sweep
   per business object), the sweep, the core precedent, the existing code to reuse (Reuse
   task), the flow around the change
2. You plan from that evidence: what the request misses (rule 1), where each business value is
   read from (rule 7), proposed validations as questions for the user (rule 8). Critical plan:
   send it with the evidence to `odoo-bug-hunter`
3. `odoo-builder` writes the code
4. Scouts collect the result: the changed methods and fields with their callers and overrides,
   access rows, `sudo()` calls, routes, the v20-pattern scan, and the Clean check on the changed files
5. You judge it; whatever rules 2-8 or 11 reject goes back to the builder first. Critical
   change: send that evidence to `odoo-reviewer`, then every blocker and should-fix to
   `odoo-verifier`
6. Report only what was confirmed

Rules:
- A scout prompt: one task, the target, the folders to search, what to return
- Opus agents get the scouts' evidence (path:line and exact code), never your conclusions;
  they open only the lines they need and search only for what the evidence lacks
- Opus agents have no `Agent` tool: only the main session dispatches scouts
- The builder's prompt names the files, methods, core precedent (path:line), sweep result,
  the existing methods to call instead of writing new ones, where each business value is read
  from, the validations the user approved (none otherwise) and what not to touch; the verifier
  gets numbered claims, and a test database only when the user named one
- Builders run in parallel only on different modules; never `isolation: worktree`
  (`custom_addons/` is not in the odoo19 repo, so a worktree has no modules)
- At once: up to 5 Haiku scouts, up to 3 Sonnet builders (different modules), up to 2 Opus
  agents; never more than 6 agents in total. In a Workflow script, enforce the same limits
- Ask the user before a run likely to pass ~1M tokens
- Never run an agent and the same search yourself

---

## Documentation Workflow

**Triggers:** the user asks how a module works, asks to learn/document a feature, or
discusses business logic.

1. **Check existing docs** — read `documentations/<module>.md`. If it covers the topic,
   answer from it. If missing or incomplete, continue.
2. **Research from source** — at least 2 core model files read, the business flow traced
   end to end, dependencies identified, key fields/methods/UI entry points located with
   file paths.
3. **Write** using `references/doc-template.md`, to `documentations/<module>.md`. Every fact
   traceable to a source file, code references as markdown links, no filler.
4. **Update** `documentations/INDEX.md`.

`documentations/` holds module and flow docs only. Plans, handoffs, work logs and review findings do not
go there.

**Developer maps** (the interactive wiring pages, one per module): build or refresh them with
`python3 docs/developer-map/build_v2.py <module-key>`, following `DEVELOPER_MAP_BLUEPRINT.md` (v2).

---

## Output Contract

| Request type | What to return |
|---|---|
| Single-file change | Complete file or exact patch |
| Full module | All files with `security/ir.model.access.csv` + rules + manifest + views |
| Review/fix | Issues list first, then corrected code |
| Quality review | Findings ranked, each tagged behavior change yes/no (`refactor.md` section 2) |
| Refactor | Plan table before any edit; per phase: changes, proof output, intended differences, deploy note (`refactor.md` sections 7-8) |

Always include the file path + method/class target for code placement.
