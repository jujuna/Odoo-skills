# Odoo 20 Project — Claude Code Instructions

## Project Structure

| Directory | Contents |
|---|---|
| `addons/` | Odoo community modules (do not modify) |
| `enterprise/` | Odoo enterprise modules (do not modify) |
| `custom_addons/` | Our custom development — this is where we build |
| `themes/` | Website themes |
| `documentations/` | Business module docs we maintain |
| `.claude/skills/odoo-dev/` | Coding standards + reference files |

## Odoo Version

**Odoo 20**, Python 3.12–3.14. Non-negotiable v20 API rules are in
`.claude/skills/odoo-dev/references/guardrails.md` — always follow them.

Odoo 20 changed several things that v19 habits get wrong. The full verified delta is in
`.claude/skills/odoo-dev/references/v20-changes.md`. The three that bite most often:

- `ir.model.access` **and** `ir.rule` are gone — one `security/ir.access.csv` replaces both,
  and it loads **last** in the manifest (groups file still loads first)
- OWL 3: `proxy()` instead of `useState()`, `t-out` instead of `t-esc`, explicit `this.` in
  templates
- `compute_sql=` makes a non-stored computed field searchable and groupable — reach for it
  before `store=True`

## Standing Rules

- **Multi-company by default.** Every model storing business data gets `company_id`,
  `check_company=True` on scoped relations, and a company restriction row in
  `ir.access.csv`. Single-company needs a stated reason.
- **Sweep before changing anything that exists.** Grep callers, overrides and inheriting
  views, and state the result. See `references/dependencies.md`.
- **Match core.** Find the same thing in `addons/`/`enterprise/` and copy the pattern. If a
  change belongs in several places, do it the way core keeps them consistent.
- **Ask before writing tests.** Say what you would cover and let us decide.

## Coding Conventions

- No emojis in output or code
- Short, direct responses — no filler
- Code references as clickable markdown links: `[file.py:42](path/file.py#L42)`
- Documentation: detailed but scannable (tables, headers, no padding)
- Don't add docstrings, comments, or type annotations to code you didn't change
- `psql SELECT` queries are pre-approved — run without asking

## Documentation Rule (always on)

Whenever Odoo business logic comes up in a session:
1. Check `documentations/<module>.md` first — answer from it if it covers the topic
2. If missing or incomplete — research from source, document it, update `documentations/INDEX.md`
3. Follow `.claude/skills/odoo-dev/references/doc-template.md` format
4. All links in docs use `../` prefix: `](../addons/...)`

### Documentation philosophy
- **Goal:** Understand the flow, purpose, and real usage — not catalog every field
- **Write for someone who wants to learn the module**, not someone grepping for field names
- Explain *how things connect* and *why they exist*, not just *what they are*
- Mention key methods only when they're essential to understanding the flow
- Skip exhaustive field/model tables — only mention fields that are decision points or non-obvious
- Configuration: document what it changes in behavior, not just the field metadata
