# Guardrails — Odoo 19+

Non-negotiable rules enforced on every code output. No exceptions.

---

## 1. Odoo 19 API — Mandatory

These APIs changed in v17–v19. Always use the new forms:

| Old (deprecated) | New (v19) | Notes |
|---|---|---|
| `read_group()` | `_read_group()` / `formatted_read_group()` | Backend tuples / web-formatted dicts; `read_group()` deprecated since 19.0 |
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
| `check_access_rights(op, raise_exception=True)` | `check_access(op)` | Raises `AccessError`; deprecated since 18.0 |
| `check_access_rights(op, raise_exception=False)` | `has_access(op)` | Returns bool; deprecated since 18.0 |
| `check_access_rule(op)` | `check_access(op)` | Merged into `check_access`; deprecated since 18.0 |
| `_filter_access_rules(op)` / `_filter_access_rules_python(op)` | `_filtered_access(op)` | Returns the allowed subset; deprecated since 18.0 |
| `_check_recursion()` / `_check_m2m_recursion(f)` | `_has_cycle(field_name=None)` | Boolean inverted — see note below; deprecated since 18.0 |
| `toggle_active()` | `action_archive()` / `action_unarchive()` | Deprecated since 19.0 |
| `self._cr` / `self._uid` / `self._context` | `self.env.cr` / `self.env.uid` / `self.env.context` | Deprecated since 19.0 |
| `group_operator='sum'` (field) | `aggregator='sum'` | Field kwarg; deprecated since 18.0, warns |
| `auto_join=True` (field) | _(removed)_ | Use `any` / `not any` domain operators |

**`_has_cycle()` inverts the old boolean.** `_check_recursion()` returned `True` when the hierarchy was *safe* (no loop); `_has_cycle()` returns `True` when a loop *exists*. Migrate the condition, not just the name:

```python
# Old
if not self._check_recursion():
    raise ValidationError(_("You cannot create recursive categories."))
# New (v19)
if self._has_cycle():
    raise ValidationError(_("You cannot create recursive categories."))
```

`_has_cycle(field_name)` covers both many2one and many2many self-relations, replacing `_check_recursion()` and `_check_m2m_recursion()`.

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

- Treat every ORM method as multi-record unless it explicitly documents and enforces singleton behavior
- Use `ensure_one()` only at singleton boundaries (single-record action payloads, value-preparation helpers)
- `create()` overrides always use `@api.model_create_multi` and call `super().create(vals_list)` once
- `write()` / `unlink()` overrides validate in batch and call `super()` once whenever possible
- Compute methods assign every record in `self`; no hidden business side effects inside computes
- Use `odoo.Command` helpers for x2many values; avoid raw `(0, 0, vals)` style in new code
- Use `odoo.fields.Domain` for dynamic domains and complex composition
- User-facing text translated with `_()`; no f-strings inside `_()`
- `_logger` uses lazy formatting (`%s`, not f-strings)
- Raw SQL is parameterized (`%s`) and cache is invalidated after SQL writes
- Raw SQL writes to compute dependencies call `records.modified(fnames)`
- Float comparisons use `float_compare` / `float_is_zero` (no direct `==`/`!=`)
- Delete restrictions use `@api.ondelete` when no cleanup side-effects needed
- No mutable default arguments
- Domain API: `from odoo.fields import Domain`
- No manual `cr.commit()` in request/button/compute/constraint/onchange code
- Manual commit requires resumable design, `_can_commit()` test guard, and cache invalidation
- All imports at module top; import inside a function only to break a circular import or defer a heavy/optional dependency (mark with `# noqa: PLC0415`)
- Minimal comments — only when naming cannot carry the meaning, kept short and explaining *why*; docstrings are one short line unless behavior is non-obvious; never add comments/docstrings/type hints to untouched code

---

## 5. Fields

- Monetary fields always paired with a `currency_id` Many2one + `currency_field='currency_id'`
- `Date.today` / `Datetime.now` as defaults WITHOUT parentheses (callable, not value)
- Many2one `ondelete` is explicitly set (`'cascade'`, `'restrict'`, or `'set null'`)
- Multi-company models: `company_id` with `index=True` and `check_company=True` on related M2O
- Related fields that are searchable/grouped have `store=True`
- Self-referential computes (depend on `parent_id.x`) must declare `recursive=True`
- Use `aggregator=` (not the deprecated `group_operator=`); `index='trigram'` for `ilike` search columns
- `@api.constrains` only fires on simple field names present in the `create`/`write` call — dotted paths are ignored; enforce always-required invariants in a `create()` override
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
- `message_post()` is singleton-only; loop deliberately for multi-record audit entries

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
type='json'                          → type='jsonrpc'
read_group()                         → _read_group() / formatted_read_group()
name_get()                           → _compute_display_name()
<tree>                               → <list>
attrs={}                             → invisible="..." / readonly="..."
fields.Date.today()  (default)       → fields.Date.today
Monetary without currency_id         → always pair them
M2O without ondelete                 → always set ondelete
sudo() without comment               → always justify
SQL with f-strings                   → always use %s params
@api.one / @api.multi                → removed since v13
@api.model on create                 → @api.model_create_multi
Missing _description                 → always set it
Missing security files               → always create them
Magic x2many tuples                  → use odoo.Command
Fragile dynamic domain lists         → use odoo.fields.Domain
cr.commit() in button/request        → transaction belongs to Odoo
check_access_rights()/_rule()        → check_access() / has_access()
_filter_access_rules()               → _filtered_access()
_check_recursion()                   → _has_cycle()  (boolean is inverted)
toggle_active()                      → action_archive() / action_unarchive()
self._cr / self._uid / self._context → self.env.cr / .uid / .context
SELECT ... FOR UPDATE (raw)          → lock_for_update() / try_lock_for_update()
```
