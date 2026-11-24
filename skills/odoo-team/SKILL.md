---
name: odoo-team
description: >
  Run an Odoo 19 task with the agent team: the main session orchestrates and decides, Haiku
  odoo-scout agents do wide and mechanical reading in parallel (up to 5), Sonnet odoo-tracer
  agents do flow sweeps and traces, Sonnet odoo-builder writes the code and runs offline checks,
  Opus odoo-bug-hunter and odoo-reviewer run for critical work, and Sonnet odoo-verifier checks
  their blockers and runs existing tests on a user-named test database. Use when the user types
  /odoo-team, or asks to use the agents, the team, or parallel scouts for the work.
---

# Odoo 19 agent team

You are the orchestrator. You plan, analyze, and decide; subagents read, write, and verify.
- **Claude Code:** agent briefs live in `.claude/agents/<agent>.md` (models are pinned in frontmatter; reasoning effort follows the user's `/effort`).
- **Antigravity / `.agents/`:** native subagent definitions live in `.agents/plugins/odoo-agents/agents/<agent>.md` (and `.agents/skills/odoo-agents/SKILL.md` documents how to invoke them with `invoke_subagent` / `swarm`).

## Output Mode (No Contradictions)

- **Default (Manager / Dev Brief — short, 5 lines + proof links):**
  1. **Purpose & change:** what changed (or was answered) with one concrete example with numbers when relevant.
  2. **Blast radius / consumers:** modules and callers verified (`path:line`).
  3. **DB / upgrade / safety risk:** schema, existing records, `ir.model.access.csv` / `ir.rule`, or external endpoints (`none` if none).
  4. **Tests & QA / i18n checks:** offline Odoo 19 check, test run summary (when user named a test DB), and any new user-visible strings (`ka_GE.po`).
  5. **Next / rollback:** next decision, rollback note, or untouched "Below our standard" proposals (Hard Rule 15).
  *Do NOT print a per-batch task board, agent tally, or process narrative in the final reply unless the user asks.*
- **Verbose Audit Trail (only when the user explicitly asks for "task board", "agent tally", "show steps", or when saving a review to `dev_notes/plans/`):** include the batch table (`# | Agent | Task | Result | Key evidence (path:line)`) and agents used by role.

---

## Workflow Order

1. **Load `odoo-dev` rules (routed — NEVER read all references upfront).**
   Before designing, read ONLY:
   - Core rules: `simplicity.md`, `dependencies.md`, `guardrails.md`, `compact-code.md`, `ai-smells.md`, `checklist.md`.
   - Area file(s) matching the task (from `odoo-dev`'s Reference Router: `fields.md`, `views.md`, `owl.md`, `security.md`, `multicompany.md`, `orm.md`, `cron.md`, `sql.md`, `controllers.md`, `testing.md` ...).
   - Coupling rows for objects in scope via `<venv-python> .claude/skills/odoo-dev/scripts/map_rows.py <term>`.
   *(In a Light Workspace without `documentations/` or DB, skip DB checks and mark external behavior `not verified — not present in this workspace`.)*

2. **Impact map first, before any design.** List every business object touched (taxes, accounts, contacts and flags, journals, payment methods, states, posted entries, payslips, declarations, bank requests). In one parallel batch:
   - pull their rows from `coupling-map.md` (`map_rows.py`);
   - launch one `odoo-tracer` per touched object for the flow sweep (`dependencies.md` Tier 4: produces, reads, configures, and DB data if a DB is named);
   - launch one `odoo-scout` to read `documentations/<module>.md` (when present) for every module in scope and quote the rules (Design Decisions, Gotchas) mentioning those objects.
   Show the user the concise impact map (`object -> modules -> what they do`) before coding. Any newly discovered coupling goes into `coupling-map.md` in the same session.

3. **Delegation rule (who reads what).**
   - Small lookup (<= 3 files or <= 300 lines): do it yourself directly.
   - Wide/mechanical reading (sweeps, extraction, checklists, file slices, core precedents): `odoo-scout` (up to 5 in parallel).
   - Flow sweeps and `super()` / OWL 2 RPC traces: `odoo-tracer`.
   - Run mechanical scripts first (`sweep.py`, `map_rows.py`) before spawning readers on large hit lists. Always open the cited `path:line` yourself before making a design decision.

4. **Critical trigger list (unified with `odoo-dev`).**
   A change is **critical** whenever it touches any of:
   - security, `security/ir.model.access.csv`, `ir.rule`, `sudo()`, or controllers / public RPC
   - money, taxes, declarations, accounting postings, or bank integrations
   - multi-company boundaries or shared master data
   - core method overrides or required/constrained fields on core models
   - states, stock valuation, or payroll flows
   For critical plans: run **`odoo-bug-hunter`** on the plan + impact map **before** coding.

5. **Implement (one module per `odoo-builder` call).**
   Give `odoo-builder` the module path, one-sentence goal, exact files/methods, core precedent (`path:line`), sweep result, and what not to touch. The builder runs `sh .claude/hooks/run_hook.sh odoo_offline_check.py --files <changed>`, `compact_scan.py`, and the `grep -En` loop scan before returning.

6. **Georgian UI strings (`i18n/ka_GE.po`).**
   When new user-visible strings were added, add only the new entries to `i18n/ka_GE.po` using plain business Georgian that matches existing terms in the same module or core (Hard Rule 13). Never overwrite existing `msgstr` entries and never leave a `.pot` file. If the module has no `ka_GE.po`, ask before creating one.

7. **Independent review & adversarial verification (critical or multi-file changes).**
   - Run **`odoo-reviewer`** on the finished diff + scouts' evidence (never hand it the builder's conclusions).
   - Run **`odoo-verifier`** on every blocker (and any should-fix that changes behavior). When the user explicitly names a test database, `odoo-verifier` runs the module's existing tests with explicit `--addons-path` and `--db_port=5432` (or `odoo.conf` port). After fixes, run verifier in `Corrected:` delta mode.

8. **Concurrency caps.** At most 5 scouts, 3 Sonnet agents (builders on distinct modules, tracers, verifier), 2 Opus agents, and **6 active subagents total** at once.
