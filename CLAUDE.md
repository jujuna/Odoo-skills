# Odoo 19 Project — Claude Code Instructions

## Project Structure

| Directory | Contents |
|---|---|
| `addons/` | Odoo community modules (do not modify) |
| `enterprise/` | Odoo enterprise modules (do not modify) |
| `custom_addons/` | Our custom development — this is where we build |
| `themes/` | Website themes |
| `documentations/` | Business module docs we maintain |
| `.claude/skills/odoo-dev/` | Coding standards + 17 reference files |

## Odoo Version

**Odoo 19**, Python 3.10+. Non-negotiable v19 API rules are in `.claude/skills/odoo-dev/references/guardrails.md` — always follow them.

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
