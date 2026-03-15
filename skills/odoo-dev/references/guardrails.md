# Guardrails — Odoo 19+

Non-negotiable rules enforced on every code output. No exceptions.

---

## 1. Odoo 19 API — Mandatory

These APIs changed in v17–v19. Always use the new forms:

| Old (deprecated) | New (v19) | Notes |
|---|---|---|
| `read_group()` | `_read_group()` | Backend aggregation |
| `name_get()` | `_compute_display_name()` | Display name override |
| `type='json'` | `type='jsonrpc'` | Controller route type |
| `<tree>` | `<list>` | XML view tag |
| `attrs={}` | `invisible="..."` / `readonly="..."` | View expressions |
| `_sql_constraints` | `models.Constraint(...)` | Named class attribute |
| `models.Index('btree', ...)` | `models.Index("(col1, col2)")` | Named class attribute |
| `@api.one` | _(removed since v13)_ | Delete it |
| `@api.multi` | _(removed since v13)_ | Delete it |
| `@api.model` on create | `@api.model_create_multi` | Batch create |
| `fields.Date.today()` (default) | `fields.Date.today` | Callable, no parens |

---

## 2. Security — Non-Negotiable

- Always define groups: `security/groups.xml`
- Always define ACLs: `security/ir.model.access.csv`
- Add record rules for scoped access, including multi-company
- In manifest `data`, security files come FIRST
- Never use unvalidated `sudo()` on user-controlled data
- Prefer ORM over SQL for business CRUD (SQL bypasses ACL/rules)
- Never build SQL with string interpolation — use `%s` params
- Restrict sensitive fields with `groups=...` on fields/views
- Do not hardcode secrets in XML/data files
- Never log passwords, tokens, or private keys
- For portal/public routes, explicitly prevent IDOR (ownership check + 404 on mismatch)

---

## 3. Performance — Non-Negotiable

- No search/read calls inside loops if batch alternative exists
- Use `search_fetch()` when reading known field sets after search
- Prefer SQL-side filtering over `.filtered(...)` on large sets
- For large batch jobs: process in chunks + savepoints + progress reporting
- When mixing ORM and SQL:
  - `flush` before SQL reads that depend on pending ORM writes
  - `invalidate` after SQL writes (`UPDATE/DELETE`)
- Keep `_order` on indexed fields and include `id` as deterministic tiebreaker

---

## 4. Python / ORM

- User-facing text translated with `_()`; no f-strings inside `_()`
- `_logger` uses lazy formatting (`%s`, not f-strings)
- Raw SQL is parameterized (`%s`) and cache is invalidated after SQL writes
- Float comparisons use `float_compare` / `float_is_zero` (no direct `==`/`!=`)
- Delete restrictions use `@api.ondelete` when no cleanup side-effects needed
- No mutable default arguments
- Domain API: `from odoo.fields import Domain`

---

## 5. Fields

- Monetary fields always paired with a `currency_id` Many2one + `currency_field='currency_id'`
- `Date.today` / `Datetime.now` as defaults WITHOUT parentheses (callable, not value)
- Many2one `ondelete` is explicitly set (`'cascade'`, `'restrict'`, or `'set null'`)
- Multi-company models: `company_id` with `index=True` and `check_company=True` on related M2O
- Related fields that are searchable/grouped have `store=True`
- `@api.onchange` used only for UX hints; real logic in `@api.depends` compute
- `copy=False` on fields that should not be duplicated (sequences, states, unique refs)

---

## 6. Views / Frontend

- `<list>` not `<tree>` in XML views
- Expression syntax (`invisible="..."`) not deprecated `attrs={}`
- `name` attribute on `<page>` and `<filter>` for stable inheritance
- `<chatter/>` present when model inherits `mail.thread`
- OWL uses current imports (`debounce` from `@web/core/utils/timing`, `onError` from `@odoo/owl`)

---

## 7. Module / Data

Minimal module layout:
- `__manifest__.py`, `models/`, `views/`, `security/`

Manifest `data` order:
1. Security (`groups.xml`, `ir.model.access.csv`, rules)
2. Core data (sequences/config/cron/templates)
3. Reports/wizards
4. Views/actions/menus

`noupdate="1"` for user-configurable records (cron defaults, templates, sequences).

---

## 8. Mail / Tracking

- `tracking=True` on business-critical state/status fields
- Bulk operations use `tracking_disable=True` in context
- `message_post()` for audit trail, not `_logger` (user-visible events)

---

## 9. Testing

For behavior changes, include or propose tests:
- At least one success path
- At least one failure/permission/validation path
- State transition assertions for workflow methods
- Security-sensitive changes must include access-scope tests

---

## 10. Never Output These Patterns

```
type='json'                      → type='jsonrpc'
read_group()                     → _read_group()
name_get()                       → _compute_display_name()
<tree>                           → <list>
attrs={}                         → invisible="..." / readonly="..."
fields.Date.today()  (default)   → fields.Date.today
Monetary without currency_id     → always pair them
M2O without ondelete             → always set ondelete
sudo() without comment           → always justify
SQL with f-strings               → always use %s params
@api.one / @api.multi            → removed since v13
@api.model on create             → @api.model_create_multi
Missing _description             → always set it
Missing security files           → always create them
```
