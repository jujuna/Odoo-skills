# Guardrails — Odoo 19

Non-negotiable rules applied to every code output. When a rule here conflicts with older
habits, or with Odoo 20 code you may have seen elsewhere, this file wins. Section 13 lists
the Odoo 20 forms that do not exist in 19.

---

## 1. API table — v19 forms only

| Wrong (old or deprecated) | Right (v19) |
|---|---|
| `check_access_rights(op, ...)` | `check_access(op)` / `has_access(op)` — deprecated since 18.0 |
| `check_access_rule(op)` | `check_access(op)` — deprecated since 18.0 |
| `_filter_access_rules(op)` / `_filter_access_rules_python(op)` | `_filtered_access(op)` — deprecated since 18.0 |
| `check_field_access_rights(op, fnames)` | `_check_field_access(field, op)` / `_has_field_access(field, op)` — deprecated since 19.0 |
| `_check_recursion()` / `_check_m2m_recursion(f)` | `_has_cycle(field_name=None)` — **boolean inverted**, deprecated since 18.0 |
| `toggle_active()` | `action_archive()` / `action_unarchive()` — deprecated since 19.0 |
| `read_group(domain, fields, groupby, lazy=...)` | `_read_group()` in Python, `formatted_read_group()` for the web — deprecated since 19.0 |
| `uom.rounding` | `env['decimal.precision'].precision_get('Product Unit')` (`rounding` is only a compute alias) |
| `name_get()` | `_compute_display_name()` |
| `type='json'` | `type='jsonrpc'` — `json` is a deprecated alias since 19.0 |
| `<tree>` | `<list>` |
| `attrs={}` | `invisible="..."` / `readonly="..."` |
| `_sql_constraints` | `models.Constraint(...)` / `models.Index(...)` class attributes |
| `@api.one` / `@api.multi` | removed since v13 — delete |
| `@api.model` on `create` | `@api.model_create_multi` |
| `fields.Date.today()` as default | `fields.Date.today` (callable, no parens) |
| `group_operator='sum'` | `aggregator='sum'` — deprecated since 18.0, warns |
| `auto_join=True` | `bypass_search_access=True` or `any` / `not any` domains |
| `self._cr` / `self._uid` / `self._context` | `self.env.cr` / `.uid` / `.context` — deprecated since 19.0 |
| `groups_id` on `ir.actions.*` | `group_ids` — renamed in 19.0, the old name breaks the XML load |
| `<t t-set>` children inside `<t t-call>` | parameters as `t-call` attributes (`x="expr"`, `x.f="text"`); the `t-set` form still works |
| `t-esc` | `t-out` in new templates; `t-esc` still renders in v19 |

**`_sql_constraints` is ignored in v19.** The registry only logs "no longer supported" and
creates no constraint ([model_classes.py:162](../../../../odoo/orm/model_classes.py#L162)).

**`_has_cycle()` inverts the old boolean.**

```python
# Old: True meant "safe"
if not self._check_recursion():
    raise ValidationError(...)
# v19: True means "there is a loop"
if self._has_cycle():
    raise ValidationError(self.env._("You cannot create recursive categories."))
```

---

## 2. Security

- Groups (and record rules) in `security/<module>_security.xml`, **first** in manifest `data`
- ACLs in `security/ir.model.access.csv`, **right after** the groups file
- Header is always `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`
- Every new model gets at least one ACL row, or nobody can use it
- No ACL row with an empty `group_id:id` — it grants every user, portal and public included
- Every multi-company model gets a **global** `ir.rule` (no `groups`) with a `company_id`
  domain — see `multicompany.md`
- Transient (wizard) models get an `ir.rule` `[('create_uid', '=', user.id)]`
- A group rule that limits users needs a `[(1, '=', 1)]` rule for the managers who imply them
- Never unvalidated `sudo()` on user-controlled data; every `sudo()` carries a one-line
  reason and is preceded by an explicit permission check
- ORM over SQL for business CRUD — SQL bypasses ACLs and record rules entirely
- SQL parameters are always `%s`, never string interpolation
- Sensitive fields carry `groups=...` on the field and in the view
- No secrets in XML/data files, never log passwords/tokens/keys
- Portal and public routes: verify ownership, return 404 (not 403) on mismatch

## 3. Multi-company

Every model that stores business data is multi-company until proven otherwise.

- `company_id = fields.Many2one('res.company', index=True, default=lambda self: self.env.company)`
- `check_company=True` on every relational field pointing at company-scoped data
- A global `ir.rule` scoping the model to `company_ids`
- Read the active company with `self.env.company`, the accessible set with `self.env.companies`
- Never `self.env.user.company_id` in business logic
- Cross-company writes go through `.with_company(company)`

Details, domains and the branch-company (`parent_of`) rules: `multicompany.md`.

## 4. Dependency safety

Before changing anything that already exists (a core method, a core field, a core view, a
public method of ours), run the sweep in `dependencies.md` and state the result in the
answer. No sweep → no change to existing behavior.

## 5. Performance

- No `search`/`read`/`write` inside a loop when a batch form exists
- `search_fetch()` when the field set is known at search time
- Filter in the domain, not with `.filtered()` on large sets
- Non-stored computed field that must be searched → a `search=` method; `store=True` only
  when it must be grouped or sorted
- Large batch jobs: chunk + `_commit_progress` + progress logging
- Mixing ORM and SQL: `flush_model()` before SQL reads, `invalidate_model()` after SQL
  writes, `modified(fnames)` when a compute dependency was written
- `_order` on indexed columns, with `id` as the final tiebreaker

## 6. Python / ORM

- Every method is multi-record unless it documents and enforces a singleton
- `ensure_one()` only at genuine singleton boundaries
- `create()` overrides: `@api.model_create_multi`, one `super().create(vals_list)`
- `write()` / `unlink()` overrides: validate in batch, one `super()` call
- Computes assign **every** record in `self`, and never write to other models
- `odoo.Command` for x2many values, never raw `(0, 0, vals)`
- `odoo.fields.Domain` for dynamic or composed domains
- `self.env._("...")` for user-facing text; never an f-string inside it
- `_logger` uses lazy `%s` formatting
- `float_compare` / `float_is_zero`, never `==` on floats
- `@api.ondelete` for delete restrictions when no cleanup is needed
- `@api.constrains` only fires on plain field names present in the `create`/`write` call —
  dotted paths are ignored; enforce always-required invariants in `create()`
- No mutable default arguments
- No `cr.commit()` in request / button / compute / constraint / onchange code
- Imports at module top; a function-level import only to break a cycle or defer a heavy
  optional dependency (mark `# noqa: PLC0415`)
- Layout, docstrings and comments: `SKILL.md` Hard Rule 11 and `compact-code.md` (one line up
  to 120 characters; docstrings only for a why, one line, three at most; no narrating
  comments; never touch them in code you did not change)

## 7. Fields

- `Monetary` always paired with a `currency_id` M2O + `currency_field='currency_id'`
- `fields.Date.today` / `fields.Datetime.now` as defaults, no parentheses
- `fields.Date.today` is the **UTC** date (the server TZ is forced to UTC, `odoo/_monkeypatches/__init__.py:57`); a date
  the user enters or sees ("booked on", "invoice date") defaults to `fields.Date.context_today`
  (`addons/account/models/account_payment.py:16`). A per-record local date (hotel, warehouse time zone):
  `fields.Date.context_today(self.with_context(tz=record.tz), timestamp)`
- Every `Many2one` sets `ondelete` explicitly
- `company_id` has `index=True`; company-scoped relations have `check_company=True`
- Related fields that are searched or grouped: `store=True`
- Self-referential computes (depending on `parent_id.x`) declare `recursive=True`
- `aggregator=`, and `index='trigram'` on columns searched with `ilike`
- `@api.onchange` for UX hints only; real logic lives in a `@api.depends` compute
- `copy=False` on sequences, states and unique references
- `Binary` fields hold base64: write `base64.b64encode(raw)`, read `base64.b64decode(rec.file)`;
  `ir.attachment` takes `'raw': raw` or `'datas': base64`

## 8. Views / frontend

- `<list>`, expression syntax, `name=` on `<page>` and `<filter>` for stable inheritance
- `<chatter/>` when the model inherits `mail.thread`
- `t-out` in new templates (QWeb and OWL); leave working `t-esc` in code you do not touch
- `t-call` parameters as attributes in new code
- OWL 2 (`addons/web/static/lib/owl/owl.js` 2.8.4): `useState` / `reactive`, `static props`
  and `static defaultProps`, `useRef("x")` + `t-ref="x"` read as `ref.el`,
  `useEffect(fn, () => deps)`, `useExternalListener`, all from `@odoo/owl` — `owl.md`
- xpaths into core OWL templates copy the **current** core attribute text
- Icons are Font Awesome: `icon="fa-check"`, `<i class="fa fa-check" title="..."/>`; view
  validation warns on an icon-only `<i>` without `title` or `aria-label` — `views.md`

## 9. Module / data

Minimal layout: `__manifest__.py`, `models/`, `views/`, `security/`.

Manifest `data` order:
1. `security/<module>_security.xml` — groups, privileges, record rules
2. `security/ir.model.access.csv` — ACLs
3. core data (sequences, config, cron, mail templates)
4. reports and wizards
5. views, actions, menus

`noupdate="1"` for records the user is expected to edit (cron defaults, templates,
sequences).

- Do **not** bump `version` in `__manifest__.py`. A version with another series prefix
  (`18.0.x.y.z`, `20.0.x.y.z`) makes the module uninstallable on 19
  (`odoo/modules/module.py:465`) — report it and change the series prefix only with the user's OK
- Do **not** write migration scripts — solve data changes with a compute, a default, or a
  fill-only-if-empty pass
- Do **not** add a README, tests or docs unless asked

## 10. Mail / tracking

- `tracking=True` on business-critical state fields
- Bulk operations run under `tracking_disable=True`
- User-visible events go to `message_post()`, not `_logger`
- `message_post()` is singleton-only — loop deliberately

## 11. Tests

Never write tests silently. When a change would normally warrant tests, **ask first**:
say which behaviors you would cover and let the user decide. If they say yes, follow
`testing.md`. Security-sensitive and money-touching changes are the cases worth pushing for.

## 12. Never output these

```
security/ir.access.csv / ir.access   → ir.model.access.csv + ir.rule XML (v20-only, section 13)
ACL row with empty group_id:id       → name a group; record scoping is an ir.rule
ir.model.access.csv before groups    → groups file first, ACLs right after
migrations/<version>/*.py            → solve it in code
version bump in __manifest__.py      → leave it alone
unrequested model/wizard/menu/test   → extend what exists, ask about tests
validation "just in case"            → propose it; the user decides (Hard Rule 8)
rate / account / tax / id in code    → read it from the owning record or xmlid (Hard Rule 7)
model without company_id             → justify it explicitly
check_company missing on a company-scoped M2O → always set it
read_group()                         → _read_group() / formatted_read_group()
name_get()                           → _compute_display_name()
type='json'                          → type='jsonrpc'
<tree> / attrs={}                    → <list> / invisible="..."
groups_id on ir.actions.*            → group_ids
_sql_constraints                     → models.Constraint(...) (v19 ignores the old one)
'version': '20.0.x.y.z'              → flag it: uninstallable on 19, ask before changing
fields.Date.today()  (default)       → fields.Date.today
Monetary without currency_id         → always pair them
M2O without ondelete                 → always set ondelete
sudo() without a reason              → justify it in one line
SQL with f-strings                   → %s parameters
@api.one / @api.multi                → removed since v13
@api.model on create                 → @api.model_create_multi
missing _description                 → always set it
magic x2many tuples                  → odoo.Command
hand-built domain lists              → odoo.fields.Domain
cr.commit() in a button/request      → the transaction belongs to Odoo
check_access_rights()/_rule()        → check_access() / has_access()
_filter_access_rules()               → _filtered_access()
_check_recursion()                   → _has_cycle()  (boolean inverted)
toggle_active()                      → action_archive() / action_unarchive()
self._cr / self._uid / self._context → self.env.cr / .uid / .context
group_operator= / auto_join=         → aggregator= / bypass_search_access=
SELECT ... FOR UPDATE (raw)          → lock_for_update() / try_lock_for_update()
any Odoo 20 form                     → the v19 form in section 13
```

**Quick scan.** Run the offline validator (`sh .claude/hooks/run_hook.sh odoo_offline_check.py --files <changed files>`) and/or `grep -En`:

```bash
grep -En \
  -e 'ir\.access\.csv' -e 'model="ir\.access"' -e "'access', '(read|write|create|unlink)'" \
  -e 'compute_sql=' -e 'models\.CachedModel' -e 'TableSQL' -e 'api\.ormcache' -e 'invalidate_ormcache' \
  -e '\.(get|set)_(str|bool|int|float)\(' -e 'user_writeable' -e 'Binary(Bytes|Value)' \
  -e '\b(has|check)_field_access\(' -e '_access_domain\(' -e 'http\.dispatcher' -e 'MockHTTPClient' \
  -e "'version': '20\." -e '(^|[^.\w])proxy\(' -e 'useProps\(' -e 'signal\.ref\(' -e '\buseListener\(' \
  -e 'useLayoutEffect' -e '@web/owl2/utils' -e 't-call-slot' -e 't-custom-portal' -e 'class="oi" data-icon=' \
  -e '<tree[ >]' -e '\bname_get\(' -e "type=[\"']json[\"']" -e '_sql_constraints' -e '\btoggle_active\(' \
  -e '\bcheck_access_rights?\(' -e '\bcheck_access_rule\(' -e '_filter_access_rules\(' -e '_check_(m2m_)?recursion\(' \
  -e 'self\._(cr|uid|context)\b' -e '@api\.(one|multi)\b' -e 'group_operator=' -e 'auto_join=' -e '\bgroups_id\b' \
  -e '\.read_group\(' -e 'numbercall' -e 'default=fields\.(Date\.today|Datetime\.now)\(\)' -e "\b_\(f[\"']" \
  <changed files>
```

Also enforce in every Python change:
- **Outbound HTTP / API calls:** always pass explicit `timeout=`, keep TLS verification enabled (`verify=True`), and use `secrets` / `consteq` for token/signature checks.
- **Exceptions & assertions:** chain re-raised exceptions (`raise UserError(...) from err`), never use `assert` for runtime validation (`python -O` strips it).

The first five lines flag Odoo 20 code (section 13), the rest old or deprecated v19 code
(sections 1 and 12). A hit is a candidate, not a verdict: comments match too. Fix hits in
lines you wrote; report hits in lines you did not touch. On 2026-10-31 all of `addons/` +
`enterprise/` (tests, `lib/`, migrations excluded) gave 21 hits, so the scan is quiet on
correct v19 code. It cannot see context (`@api.model` on `create`, a `sudo()` reason,
company scoping, a missing ACL or rule); those still need reading.

## 13. v20-only APIs — never use in v19

Odoo 20 forms that do not exist in v19 (checked against `odoo/`, `addons/`, `enterprise/` of
this tree). Code copied from an Odoo 20 tree, or written from v20 habits, must use the right
column.

| Odoo 20 form | v19 form |
|---|---|
| `security/ir.access.csv`, model `ir.access`, columns `model_id,group_id/id,operation,domain` | `security/ir.model.access.csv` (`model_id:id,group_id:id,perm_read,...`) + `ir.rule` records in XML |
| restriction row (empty `group_id`) / permission row with `domain` | global `ir.rule` (no `groups`) / group `ir.rule` |
| `ir.access.csv` **last** in the manifest | groups file first, `ir.model.access.csv` right after |
| domain operator `('order_id', 'access', 'read')` | repeat the parent's domain through the field: `('order_id.partner_id', ...)` |
| `res.groups.access_ids` | `model_access` (ACLs) + `rule_groups` (rules) |
| public `check_field_access(f, op)` / `has_field_access(f, op)` | `_check_field_access(f, op)` / `_has_field_access(f, op)` |
| `Model._access_domain(op)` | `env['ir.rule']._compute_domain(model_name, op)` |
| `@api.ormcache(...)` (`from odoo import api`) | `from odoo.tools import ormcache` → `@ormcache(...)` |
| `env.transaction.invalidate_ormcache('x')` | `self.env.registry.clear_cache('x')` |
| `odoo.http.dispatcher.serialize_exception` | `odoo.http.serialize_exception` |
| `ir.config_parameter` `get_str` / `get_bool` / `get_int` / `get_float`, `set_*` | `get_param(key, default)` (returns a string; `== 'True'`, `int(...)`) / `set_param(key, value)` |
| field parameter `user_writeable=True` | extend `res.users` `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` |
| public `read_group(domain, groupby, aggregates, ...)` | `_read_group(domain, groupby, aggregates, ...)`; v19 `read_group` is the deprecated old `fields`/`lazy` signature |
| `_read_group_select(table, spec)`, `_read_group_groupby(table, spec)`, `_order_to_sql(table, order, reverse)` (`TableSQL`) | `_read_group_select(spec, query)`, `_read_group_groupby(alias, spec, query)`, `_order_to_sql(order, query, alias, reverse)` |
| `compute_sql=` on a computed field | `search=` method; `store=True` when it must be grouped or sorted |
| `models.CachedModel` | a plain model with an `@ormcache` method |
| `BinaryBytes(raw)` / `rec.file.content` | `base64.b64encode(raw)` / `base64.b64decode(rec.file)` |
| `ir.attachment` `datas` removed | `datas` (base64) and `raw` both work |
| OWL 3 `proxy(obj)` | `useState(obj)` / `reactive(obj)` |
| `props = useProps(schema)` | `static props = {...}` / `static defaultProps = {...}` |
| `useLayoutEffect(fn, () => deps)` from `@web/owl2/utils` | `useEffect(fn, () => deps)` from `@odoo/owl` |
| `useEnv` / `useSubEnv` / `onWillRender` from `@web/owl2/utils` | from `@odoo/owl` |
| `x = signal.ref()` + `t-ref="this.x"` + `this.x()` | `useRef("x")` + `t-ref="x"` + `ref.el` |
| `useListener(target, ev, fn)` | `useExternalListener(target, ev, fn)` |
| `t-call-slot` / `t-custom-portal` | `t-slot` / `t-portal` |
| Material Symbols: `<i class="oi" data-icon="check"/>`, `icon="search"` | Font Awesome: `<i class="fa fa-check"/>`, `icon="fa-search"` |
| view type `card` | none — use `kanban` |
| `account.payment.state` `paid` (posted) / `reconciled` (matched) | `in_process` (posted) / `paid` (matched) |
| `account_number`, `sanitized_account_number`, `journal.bank_account_number` | `acc_number`, `sanitized_acc_number`, `journal.bank_acc_number` |
| `partner._display_address(without_name=True, separator=' ')` | `partner._display_address(without_company=True)` |
| computed `is_company`, no `company_type` | `company_type` selection, writable `is_company` |
| untagged test classes run `post_install` | untagged test classes run `at_install` |
| `MockHTTPClient` (tests) | none — patch the HTTP call |
| cron `MIN_TIME_PER_JOB` 120 s | 10 s |
| manifest `version` `'20.0.x.y.z'` | `'19.0.x.y.z'` or a short `'1.0'` |

Sources: [ir_rule.py](../../../../odoo/addons/base/models/ir_rule.py),
[ir_model.py:2095](../../../../odoo/addons/base/models/ir_model.py#L2095),
[models.py:1959](../../../../odoo/orm/models.py#L1959), [:2021](../../../../odoo/orm/models.py#L2021),
[:2755](../../../../odoo/orm/models.py#L2755), [:3375](../../../../odoo/orm/models.py#L3375),
[:5243](../../../../odoo/orm/models.py#L5243),
[ir_config_parameter.py:60](../../../../odoo/addons/base/models/ir_config_parameter.py#L60),
[res_users.py:176](../../../../odoo/addons/base/models/res_users.py#L176),
[res_groups.py:24](../../../../odoo/addons/base/models/res_groups.py#L24),
[http.py:469](../../../../odoo/http.py#L469),
[account_payment.py:36](../../../../addons/account/models/account_payment.py#L36),
[res_bank.py:90](../../../../odoo/addons/base/models/res_bank.py#L90),
[res_partner.py:1202](../../../../odoo/addons/base/models/res_partner.py#L1202),
[ir_cron.py:34](../../../../odoo/addons/base/models/ir_cron.py#L34),
[tests/common.py:317](../../../../odoo/tests/common.py#L317),
[owl.js](../../../../addons/web/static/lib/owl/owl.js) exports at line 6343.
