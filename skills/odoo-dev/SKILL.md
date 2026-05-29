---
name: odoo-dev
description: >
  Use this skill for Odoo 19+ development tasks: create, modify, review, debug, refactor, secure,
  optimize, or migrate modules and code (models, views, controllers, wizards, reports, manifests,
  ACLs/rules, cron, QWeb, OWL, ORM/SQL, integrations). Trigger on Odoo-specific terms like
  __manifest__.py, ir.model.access, record rules, model/view inheritance, jsonrpc/JSON-2 API,
  performance, security, and customization requests.
  Also triggers for Odoo business module learning, documentation requests, and "how does X work in Odoo".
---

# Odoo 19+ Development Skill

Produce production-grade Odoo 19+ code. Keep this file compact — load references on demand.

## Reference Router

Load **only** the reference file(s) needed for the current task:

| Task area | File |
|---|---|
| ACLs, record rules, sudo, portal, IDOR | `references/security.md` |
| ORM correctness, recordsets, overrides, domains, transactions, multi-company | `references/orm.md` |
| N+1 fixes, batching, cache, profiling | `references/performance.md` |
| Python language style, logging, errors, inheritance | `references/python.md` |
| Commit safety, savepoints, rollback, cache/recompute after SQL | `references/transactions.md` |
| Field types, compute, inverse, onchange, constraints | `references/fields.md` |
| Raw SQL, indexes, query plans, migrations | `references/sql.md` |
| Full module skeleton / boilerplate | `references/scaffold.md` |
| OWL components, services, hooks, frontend tests | `references/owl.md` |
| XML views, inheritance, expressions, QWeb reports | `references/views.md` |
| HTTP/JSON-RPC controllers, JSON-2 API, portal | `references/controllers.md` |
| Wizards (TransientModel), multi-step, actions | `references/wizards.md` |
| mail.thread, tracking, message_post, activities | `references/mail.md` |
| Scheduled actions (cron), batch jobs, progress | `references/cron.md` |
| XML/CSV data files, noupdate, sequences, actions | `references/data-files.md` |
| Unit/integration tests, Form simulation | `references/testing.md` |
| Business module learning / documentation | `references/doc-template.md` |
| v19 API rules, deprecations, banned patterns | `references/guardrails.md` |
| Pre-output quality check | `references/checklist.md` |

**Auto-load rules:**
- Full module request → read `scaffold.md` first
- Write tests → read `testing.md` first
- Fields/compute/onchange → read `fields.md` first
- Any non-trivial Python ORM code → read `orm.md`
- Performance-sensitive ORM code → read `orm.md` + `performance.md`
- Manual commit/savepoint/raw SQL cache work → read `transactions.md`
- Any code output → apply `guardrails.md` rules (internalized — load only when unsure)

---

## Execution Workflow

1. **Identify task type:** `build` | `fix` | `review` | `security` | `performance` | `migration` | `frontend` | `learn/document`
2. **For `learn/document`:** run Documentation Workflow below
3. **For code tasks:** load matching reference file(s) — not all files
4. **For Python ORM code:** optimize for batch correctness first, then readability, then micro-performance
5. **Apply guardrails** from `references/guardrails.md`
6. **Generate minimal, correct code** for the request scope
7. **Run checklist** from `references/checklist.md` before returning

---

## Documentation Workflow

**Triggers:** user asks how a module works, asks to learn/document a feature, or discusses business logic.

### Step 1 — Check existing docs
Read `documentations/<module-name>.md`. If it covers the topic, answer from it. If missing/incomplete, proceed.

### Step 2 — Research from source
Read actual Odoo source code. Required evidence:
- At least 2 core model files read
- Business flow traced end-to-end
- Dependencies identified
- Key fields, methods, UI entry points found with file paths

### Step 3 — Write documentation
Use `references/doc-template.md` as format. Write to `documentations/<module-name>.md`.
- Every fact traceable to a source file
- Code references as markdown links
- No filler — every sentence carries information

### Step 4 — Update index
Always update `documentations/INDEX.md`.

---

## Output Contract

| Request type | What to return |
|---|---|
| Single-file change | Complete file or exact patch |
| Full module | All files with security + manifest + views |
| Review/fix | Issues list first, then corrected code |
| Refactor | Behavior-stable unless user requests change |

Always include file path + method/class target for code placement.
