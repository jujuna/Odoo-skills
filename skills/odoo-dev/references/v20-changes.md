# Odoo 19 → 20 Delta

Everything below was verified against this checkout (`19.0` vs `20.0` branch). Paths are
clickable from the repo root. Load this file when migrating code, when reviewing code that
looks like it was written for v19, or when unsure whether an API still exists.

Framework version: `version_info = (20, 0, 0, FINAL, 0, '')` — [odoo/release.py:15](../../../../odoo/release.py#L15)
Python: **3.12 – 3.14** (`MIN_PY_VERSION = (3, 12)`, `MAX_PY_VERSION = (3, 14)`) — the ORM uses
PEP 695 generics (`def mapped[T](...)`), so 3.11 will not even import.

---

## 1. Security was rebuilt — the single biggest change

`ir.model.access` **and** `ir.rule` are gone. Both are replaced by one model, `ir.access`,
defined in [odoo/addons/base/models/ir_access.py](../../../../odoo/addons/base/models/ir_access.py).

| v19 | v20 |
|---|---|
| `security/ir.model.access.csv` | `security/ir.access.csv` |
| `security/*_security.xml` with `<record model="ir.rule">` | same CSV, `domain` column |
| `perm_read,perm_write,perm_create,perm_unlink` (4 bool columns) | one `operation` column, a subset of `crud` |
| `model_id:id` = `model_sale_order` (xmlid) | `model_id` = `sale.order` (the model name) |
| `group_id:id` | `group_id/id` |
| global rule = `ir.rule` with no `groups` | **restriction** = `ir.access` row with empty `group_id` |
| group rule = `ir.rule` with `groups` | **permission** = `ir.access` row with a `group_id` |

Counts in this checkout: 506 `ir.access.csv` files, 0 `ir.model.access.csv`.

The one canonical header, identical in all 506 core files:

```csv
id,name,model_id,group_id/id,operation,domain
```

Full rules, semantics and templates: `security.md`.

### New `access` domain operator

`('order_id', 'access', 'read')` means *"the user must have `read` on the related
`order_id` record"*. It replaces hand-written cross-model rule domains and it is what
core now uses for line models —
[addons/sale/security/ir.access.csv:36](../../../../addons/sale/security/ir.access.csv#L36).
Works on `many2one` fields and on `id` only —
[odoo/orm/domains.py:1921](../../../../odoo/orm/domains.py#L1921).

### Manifest order flipped

`security/ir.access.csv` is loaded **last**, after views and menus. Group definitions
(`security/<module>_security.xml`) stay **first**. Verified in `account`, `stock`,
`project`, `hr`, `purchase`, `mail`, `sale` — in every one, the groups file is entry `0`
and `ir.access.csv` is the last entry.

---

## 2. Removed APIs — using these is a hard error in v20

| Removed | Use instead |
|---|---|
| `check_access_rights(op, raise_exception=True)` | `check_access(op)` |
| `check_access_rights(op, raise_exception=False)` | `has_access(op)` |
| `check_access_rule(op)` | `check_access(op)` |
| `_filter_access_rules(op)` / `_filter_access_rules_python(op)` | `_filtered_access(op)` |
| `check_field_access_rights(op, fnames)` | `check_field_access(field, op)` / `has_field_access(field, op)` |
| `_check_recursion()` / `_check_m2m_recursion(f)` | `_has_cycle(field_name=None)` — **boolean inverted** |
| `toggle_active()` | `action_archive()` / `action_unarchive()` |
| `copy_translations()` | — (no replacement; translations follow `copy()`) |
| `odoo.tools.ormcache` | `odoo.api.ormcache` (`from odoo import api`) |
| `odoo.tools.ormcache_context` | `@api.ormcache('self.env.context.get("lang")')` |
| `registry.clear_cache(name)` | `self.env.transaction.invalidate_ormcache(name)` |
| `odoo.tools.Query` | `odoo.models.Query` |
| `api.deprecated` | `odoo.tools.func.deprecated` |
| `api.Self` | `typing.Self` |
| `odoo.http.serialize_exception` | `odoo.http.dispatcher.serialize_exception` |
| `odoo.tools.populate` | `odoo.tools.duplicate` |
| `uom.uom.rounding` | `env['decimal.precision'].precision_get('Product Unit')` |
| `_read_group_fill_results` / `_read_group_fill_temporal` / `_read_group_format_result` | web layer only — [addons/web/models/models.py](../../../../addons/web/models/models.py) |
| OWL 2 `useState` / `reactive` | OWL 3 `proxy` |
| QWeb `t-esc` / `t-raw` (server side too) | `t-out`. v19 had `_compile_directive_esc`; v20 does not. The engine only logs "Unknown directives or unused attributes" and renders **nothing** — reports and wizard HTML come out blank, no error ([ir_qweb.py:1929](../../../../odoo/addons/base/models/ir_qweb.py#L1929)) |
| `_sql_constraints` | `models.Constraint(...)`. v20 logs "no longer supported" and creates **no** constraint — uniqueness is silently unenforced |
| `ir.config_parameter.get_param(key, default)` / `set_param(key, value)` | typed `get_str` / `get_bool` / `get_int` / `get_float(key, default)` and `set_str` / `set_bool` / `set_int` / `set_float(key, value)` — commit `a4f2879697a`, [ir_config_parameter.py:65-129](../../../../odoo/addons/base/models/ir_config_parameter.py#L65). The module still installs; the cron or button that reads the key dies with `AttributeError` at run time. `set_bool(key, False)` stores `'False'` (v19 `set_param(key, False)` deleted the row); only `None` means undefined. A settings `Boolean` with `config_parameter=` and `default=True` shows ON while the key is missing ([res_config.py:264](../../../../odoo/addons/base/models/res_config.py#L264)) — code reading the key must use the same default, or drop the field default |
| `res.users.SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` | field parameter `user_writeable=True` — commit `a816d151ae1`, [res_users.py:189](../../../../odoo/addons/base/models/res_users.py#L189), [:638](../../../../odoo/addons/base/models/res_users.py#L638). Overriding the old properties is silently ignored: the user can no longer save that field on their own record (only `base.group_erp_manager` can). Reads follow record rules, and every internal user reads every user ([base ir.access.csv:70](../../../../odoo/addons/base/security/ir.access.csv#L70)), so a secret stored on `res.users` needs `groups=` |
| Font Awesome (`fa fa-x`, `icon="fa-x"`) | Material Symbols — see §10 and `views.md` |

**Porting `get_param` reads.** Pick the getter by how the value is used. The typed getters
are not exact renames:

| v19 read | v20 | Trap |
|---|---|---|
| `get_param(key, 'B')` | `get_str(key, 'B')` | v19 returned `raw or default`, so a stored `''` gave the default. `get_str` returns `''`; only a missing row or a NULL value gives the default ([ir_config_parameter.py:124](../../../../odoo/addons/base/models/ir_config_parameter.py#L124)) |
| `get_param(key) == 'True'` | `get_bool(key, False)` | parsed by `str2bool`, so `'1'`, `'true'`, `'yes'`, `'on'` now read True ([misc.py:456](../../../../odoo/tools/misc.py#L456)) |
| `float(get_param(key))` inside `try/except ValueError` | `get_float(key, default)` | a non-numeric value already returns the default and logs a WARNING ([ir_config_parameter.py:149](../../../../odoo/addons/base/models/ir_config_parameter.py#L149)). Drop the wrapper |

A `res.config.settings` `get_values()` override that re-reads a `config_parameter=` field is
dead code in v20: core `default_get` already reads every such field with the typed getter and
the field default ([res_config.py:263-286](../../../../odoo/addons/base/models/res_config.py#L263)).
Delete the override instead of porting it.

`odoo.tools` only re-exports `SQL` and `drop_view_if_exists` from `tools.sql` now;
`from odoo.tools import *` no longer pulls in the whole SQL helper set —
[odoo/tools/\_\_init\_\_.py:15](../../../../odoo/tools/__init__.py#L15).

---

## 3. `read_group()` is back — and it is no longer deprecated

This reverses the v19 guardrail. In v20 there are three layers:

| Method | Where | Returns | Use it for |
|---|---|---|---|
| `read_group(domain, groupby, aggregates, having, offset, limit, order)` | `@typing.final @api.model`, [odoo/orm/models.py:1932](../../../../odoo/orm/models.py#L1932) | list of tuples, relational values as **ids** | RPC / external callers |
| `_read_group(...)` — same signature | [odoo/orm/models.py:1996](../../../../odoo/orm/models.py#L1996) | list of tuples, relational values as **recordsets** | all backend Python |
| `formatted_read_group(...)` | [addons/web/models/models.py:1022](../../../../addons/web/models/models.py#L1022) | web-formatted dicts | the web client |

The old v16 signature (`fields=`, `groupby=`, `lazy=True`, returning dicts) is gone for good.
Keep using `_read_group()` in server code — `read_group()` is the public wrapper, not a
replacement for it.

Also available (already in 19, still the right tool for multi-level aggregation in one
round-trip): `_read_grouping_sets(domain, grouping_sets, aggregates, order)`.

---

## 4. Signature changes — `Query` → `TableSQL`

Group-by and order hooks now receive a `TableSQL` object instead of `(alias, query)`:

```python
# v19
def _read_group_select(self, aggregate_spec, query): ...
def _read_group_groupby(self, alias, groupby_spec, query): ...
def _read_group_having(self, having_domain, query): ...
def _read_group_orderby(self, order, groupby_terms, query): ...
def _order_to_sql(self, order, query, alias=None, reverse=False): ...

# v20
def _read_group_select(self, table: TableSQL, aggregate_spec): ...
def _read_group_groupby(self, table: TableSQL, groupby_spec): ...
def _read_group_having(self, table: TableSQL, having_domain): ...
def _read_group_orderby(self, table: TableSQL, order, groupby_terms): ...
def _order_to_sql(self, table: TableSQL, order, reverse=False): ...
```

`TableSQL` supports **dotted traversal that auto-joins**: `table.company_id.currency_id`
produces the joined SQL expression. This is what makes `compute_sql` (below) short.

Other renames on `BaseModel`:

| v19 | v20 |
|---|---|
| `_has_field_access(field, op)` | `has_field_access(field, op)` (public) |
| `_check_field_access(field, op)` | `check_field_access(field, op)` (public) |
| `concat(*args)` / `union(*args)` | also accept one iterable: `union(list_of_recordsets)` |
| `_rec_names_search = ['name']` | `_rec_names_search = ('name',)` — tuple |

New: `models.get_public_method(model, name)` (replaces `check_method_name`),
`Model._access_domain(operation)` (the cached access domain, replaces reading `ir.rule`).

---

## 5. New: `compute_sql` — searchable/groupable computed fields without `store=True`

The highest-value new field attribute in v20. A non-stored computed field with
`compute_sql` becomes searchable, groupable and orderable, because the ORM can express it
in SQL. 82 core fields already use it.

```python
currency_id = fields.Many2one(
    'res.currency', 'Currency',
    compute='_compute_currency_id',
    compute_sql='_compute_sql_currency_id',
    compute_sudo=True,          # mandatory when compute_sql is set
)

@api.depends('company_id')
def _compute_currency_id(self):
    for template in self:
        template.currency_id = template.company_id.sudo().currency_id or main_currency

def _compute_sql_currency_id(self, table):
    main_company = self.env['res.company']._get_main_company()
    return SQL("COALESCE(%s, %s)", table.company_id.currency_id, main_company.currency_id.id)
```

[addons/product/models/product_template.py:99](../../../../addons/product/models/product_template.py#L99)

Rules enforced by the framework ([odoo/orm/fields.py:471](../../../../odoo/orm/fields.py#L471)):
- `compute_sql` only makes sense on a field that also has `compute`
- `compute_sudo` must be passed **explicitly** (warning otherwise)
- the method must return an `SQL` object

Prefer, in this order: plain compute → `compute_sql` → `search=` method → `store=True`.
`store=True` only when the value is genuinely stable and read far more often than written.

Also new: `init_storage=` (how a new column is populated at install time).

---

## 6. New: `models.CachedModel`

A Python-only mixin for small, rarely-changing reference tables (currencies, countries,
UoM-style data). It caches a fixed field set in the `'stable'` ormcache and serves reads
from it — [odoo/orm/models_cached.py](../../../../odoo/orm/models_cached.py).

```python
class MyRef(models.CachedModel):
    _name = 'my.ref'
    _cached_data_domain = []
    _cached_data_fields = ('code', 'name')   # no translated, context- or model-dependent fields
```

Do not reach for it by default. It is for data read on nearly every request.

---

## 7. ormcache moved and is now transaction-aware

```python
from odoo import api

@api.ormcache('self.env.company.id', 'code')       # default bucket
def _get_config(self, code): ...

@api.ormcache(cache='stable')                      # named bucket, invalidated separately
def _get_all_access(self): ...
```

Invalidation: `self.env.transaction.invalidate_ormcache('stable')`.
`registry.clear_cache()` is gone. The transaction also exposes
`invalidate_access_cache(model_name='')`, `clear()` and `reset()` —
[odoo/orm/environments.py:833](../../../../odoo/orm/environments.py#L833).

---

## 8. QWeb: `t-call` takes parameters as attributes

The nested `<t t-set>`-before-`t-call` idiom is replaced by attributes on the `t-call`
itself:

```xml
<!-- v19 -->
<t t-call="web.brand_promotion_message">
    <t t-set="_utm_medium">portal</t>
</t>

<!-- v20 -->
<t t-call="web.brand_promotion_message" _message.translate="" _utm_medium.f="portal"/>
```

| Suffix | Meaning |
|---|---|
| `name="expr"` | Python expression |
| `name.f="text"` | format string / literal |
| `name.translate="text"` | translatable literal |

[addons/web/views/webclient_templates.xml:103](../../../../addons/web/views/webclient_templates.xml#L103)

---

## 9. OWL 2 → OWL 3

`addons/web/static/lib/owl/owl.js` reports `3.0.0-alpha.49`. This is a different
reactivity model, not a version bump. See `owl.md` for the working rules.

| OWL 2 | OWL 3 |
|---|---|
| `useState(obj)` / `reactive(obj)` | `proxy(obj)` from `@odoo/owl` |
| `static props` / `static defaultProps` | `props = useProps(schema)` — the static form **throws** in the component constructor ([owl3_compatibility_layer.js:45](../../../../addons/web/static/src/owl2/owl3_compatibility_layer.js#L45)); field widgets use `useProps(standardFieldProps)`, client actions `useProps(standardActionServiceProps)` |
| `useEffect(fn, deps)` | `useLayoutEffect(fn, () => deps)` from `@web/owl2/utils`. `@odoo/owl` still exports a `useEffect(fn)`, but it is a new one-argument reactive effect — a deps argument is silently ignored |
| `useEnv`, `useSubEnv`, `onWillRender` | from `@web/owl2/utils` — its **only** exports are these three plus `render` and `useLayoutEffect` ([owl2/utils.js](../../../../addons/web/static/src/owl2/utils.js)) |
| `useRef("x")` + `t-ref="x"` + `ref.el` | `x = signal.ref()` + `t-ref="this.x"` + `this.x()` — `.el` is `undefined`, no error |
| `useExternalListener(target, ev, fn)` | `useListener(target, ev, fn)` from `@odoo/owl` (351 core uses) |
| `useComponent`, `useChildSubEnv`, `onRendered` | gone — no export anywhere, 0 imports in core |
| `t-esc` | `t-out` |
| `t-slot` | `t-call-slot` |
| `t-portal` | `t-custom-portal` |
| `t-ref`, `t-model` | directive names unchanged (core: `t-ref` 887, `t-custom-ref` 0; `t-model` 29) — only the `t-ref` value changed |
| implicit `this` in templates | explicit `this.props.x`, `this.state.x` |

Importing a name `@odoo/owl` no longer exports does not fail the bundle — the binding is
`undefined` and the component throws when `setup()` calls it. Full export list and the
migration procedure are in `owl.md`.

New core primitives: `computed`, `signal`, `t`, `useProps`, `useOnChange`, plugins
(`usePlugin`), scopes, resources. Counts in `addons/web/static/src`: `useState` 0,
`proxy(` 146, `t-esc` 2, `@web/owl2/utils` imports 58.

**v19 xpaths into core OWL templates stop matching.** Core templates now say
`t-component="this.props.Renderer"`, `t-if="this.model.isReady()"`, so a v19 xpath such as
`//t[@t-component='props.Renderer']` matches nothing and the view crashes with
"cannot be located in element tree". Rewrite every xpath against the v20 attribute text.

---

## 10. Smaller changes worth knowing

- **New view type `card`** — `ir.ui.view.type` selection now includes `('card', "Card")`,
  [odoo/addons/base/models/ir_ui_view.py:164](../../../../odoo/addons/base/models/ir_ui_view.py#L164).
- **`odoo.http` is a package** — `odoo/http/{dispatcher,router,session,stream,...}.py`.
  Route types unchanged: `type='http'`, `type='jsonrpc'` (422 core usages), plus the
  `/json/2/<model>/<method>` external API.
- **Cron**: `MIN_TIME_PER_JOB` 10 s → 120 s; failing crons now notify the admin before
  being deactivated; each job runs in its own `contextvars` context —
  [odoo/addons/base/models/ir_cron.py](../../../../odoo/addons/base/models/ir_cron.py).
- **`res.groups`**: `model_access` / `rule_groups` → `access_ids`; `privilege_id` is
  labelled "Scope" in the UI; disjoint-group validation is stricter.
- **UoM has no `rounding` field** — round quantities with
  `precision_digits=env['decimal.precision'].precision_get('Product Unit')`.
- **`odoo.tools.binary`**: new `BinaryBytes` / `BinaryValue` wrappers.
- **Tests**: new `MockHTTPClient` context manager in
  [odoo/tests/common.py](../../../../odoo/tests/common.py) for asserting outbound HTTP.
- **`odoo.tools.safe_eval` is a package** (`evaluation`, `expression`, `runtime`).
- **Font Awesome is removed — icons are Material Symbols** (commit `3e15a7be694`). Icons are
  font ligatures: `<i class="oi" data-icon="check"/>`, not `class="fa fa-check"`. Button
  `icon=` takes the Material Symbols name directly (`icon="search"`, `icon="refresh"`,
  `icon="edit_square"`) — [view_button.js:24](../../../../addons/web/static/src/views/view_button/view_button.js#L24)
  copies it into `data-icon` as-is. The temporary `fa-` mapping is gone, so a leftover
  `icon="fa-search-plus"` renders as broken text (`-🔍-`). Brand/custom icons use the `oi_`
  prefix (`data-icon="oi_github"`); `oi-filled`, `oi-fw`, `oi-lg`, `oi-spin` replace the
  `fa-` utility classes — [icons.scss](../../../../addons/web/static/src/webclient/icons.scss).
  Only names in the shipped font subset render — the list is `ICONS` in
  [addons/web/icons.py](../../../../addons/web/icons.py). SCSS keyed on `.fa-x` must move to
  `[data-icon="x"]`, and view validation warns when an `<i data-icon>` has no `title`,
  `aria-label` or text. Mapping table and rules: `views.md` → Icons.
- **Manifest `version` must start with `20.0.`** — [odoo/modules/module.py:500](../../../../odoo/modules/module.py#L500)
  (`check_version`, [module.py:598](../../../../odoo/modules/module.py#L598)) logs "The module X has
  an incompatible version, setting installable=False" and the module shows **uninstallable**
  before any of its code is read. Short versions (`'1.0'`) are adapted to the running series
  and are fine; a hard-coded `19.0.x.y.z` is not. Changing the series prefix is a migration
  step, not a "version bump" — flag it and ask before editing.

---

## 11. Accounting: payments, bank accounts, statements

Found while porting `basis_bank` (2026-09-23). Each one breaks v19 code at import, at registry
setup or silently at run time.

**`account.payment.state` lost `in_process`** — v20 selection is `draft, paid, reconciled,
canceled, rejected` ([account_payment.py:37](../../../../addons/account/models/account_payment.py#L37)).

| v19 | v20 | Meaning |
|---|---|---|
| `in_process` | `paid` | posted, waiting for the bank statement |
| `paid` | `reconciled` | matched with the statement (or all its bills paid) |

- Writing `'in_process'` raises `ValueError: Wrong value` ([fields_selection.py:231](../../../../odoo/orm/fields_selection.py#L231)).
  A search on it silently matches nothing.
- Rename in two steps: `'paid'` → `'reconciled'` first, then `'in_process'` → `'paid'`. A blind
  `in_process` → `paid` replace turns every old `state == 'paid'` check into "any posted payment".
- `action_post()` sets `paid` for every payment. v19 sent `asset_cash` outstanding accounts straight to paid.
- `action_validate()` now means paid → `reconciled`. It raises for `asset_cash` outstanding
  accounts and for any state other than `paid` ([account_payment.py:1221](../../../../addons/account/models/account_payment.py#L1221)).
- `_valid_payment_states()` moved from `account.batch.payment` to `account.payment` and now returns
  `['paid', 'reconciled']` or `['paid']` ([account_payment.py:290](../../../../addons/account/models/account_payment.py#L290)).
- Journal items and the move use `commercial_partner_id`, not `partner_id`. Recipient bank
  accounts come from `commercial_partner_id.bank_ids`.

**`account.move.line.amount_residual` is computed on every line**, not only on reconcilable and
cash accounts ([account_move_line.py:1210](../../../../addons/account/models/account_move_line.py#L1210)).
A payment whose outstanding account is not reconcilable keeps a non-zero liquidity residual and stays `paid`.

**`res.bank` is deleted** — commit `113d77eb35aa` "[IMP] *: Improve UX of bank accounts".

| v19 | v20 |
|---|---|
| `res.bank` model, `res.partner.bank.bank_id` | gone. `bank_name`, `bank_bic` (free Char, uppercased on save) and the address live on `res.partner.bank` ([res_partner_bank.py:59](../../../../odoo/addons/base/models/res_partner_bank.py#L59)) |
| `acc_number` / `sanitized_acc_number` / `acc_holder_name` | `account_number` / `sanitized_account_number` / `holder_name` |
| `account.journal.bank_id` / `bank_acc_number` | `bank_bic` / `bank_name` / `bank_account_number`, related to `bank_account_id` ([account_journal.py:249](../../../../addons/account/models/account_journal.py#L249)) |
| `from odoo.addons.base.models.res_bank import sanitize_account_number` | `...base.models.res_partner_bank import ...` — the old path fails at import |

`@api.depends('bank_id.bic')` on a journal fails registry setup with "Wrong @depends"
([fields.py:949](../../../../odoo/orm/fields.py#L949)). A typed BIC can be 8 or 11 characters
(`CBASGE22` or `CBASGE22XXX`), so compare `bank_bic[:8]`.

**Bank feeds**: the name-mangled `__get_bank_statements_available_sources` is gone. Override
`_get_bank_statements_available_sources` ([account_journal.py:57](../../../../addons/account/models/account_journal.py#L57)).
A leftover `__` override is never called: the option disappears from the dropdown, but writing
its value still works, because a method-based selection is not validated on write
([fields_selection.py:231](../../../../odoo/orm/fields_selection.py#L231) skips the check when
`_selection` is `None`). A static-list selection such as `account.payment.state` does raise.

**`_create_bank_statements()` returns three values**: `(statement_ids, ignored_duplicates,
ignored_zero_amount)`. Zero-amount lines are now skipped
([account_bank_statement_import/models/account_journal.py:282](../../../../enterprise/account_bank_statement_import/models/account_journal.py#L282)).
Unpacking two values raises after the statements were already created.

**Reconcile a statement line from code** the way the bank widget does:
`st_line.set_line_bank_statement_line(aml_ids)`
([account_accountant/models/account_bank_statement.py:1720](../../../../enterprise/account_accountant/models/account_bank_statement.py#L1720)).
It skips lines that are already reconciled. Bank-API precedent for payment states:
`account_online_payment` maps bank pending/accepted to `paid` and leaves `reconciled` to
statement matching (`ONLINE_STATUS_TO_STATE`).

Also proven while installing the gec modules on a test database (2026-09-23):

- **`account.group` is deleted** — commit `c3313b336b9f` "[IMP] account: Replace account groups
  with account parent". `_inherit = 'account.group'` stops the registry with "Model
  'account.group' does not exist in registry".
- **OdooBot cannot trust bank accounts**: `res.partner.bank._user_can_trust()` refuses uid 1
  outside install or test mode ([res_partner_bank.py:317](../../../../addons/account/models/res_partner_bank.py#L317)),
  so crons and `odoo-bin shell` scripts must use a real user (`with_user(...)`) to set
  `allow_out_payment`.
- Payroll: `hr.salary.rule.category_id` no longer exists and the xmlid
  `hr_payroll.hr_payslip_run_view_kanban` is gone (replacements not checked yet).

Found while planning the `l10n_ge` merge of `gec_localization` + `gec_l10n_ge_tax` (2026-09-23):

- **Withholding field renames** in `l10n_account_withholding_tax`: `account.tax.is_withholding_tax_on_payment`
  → `is_withholding_tax` ([account_tax.py:13](../../../../addons/l10n_account_withholding_tax/models/account_tax.py#L13));
  `account.payment.should_withhold_tax` (Boolean) → `withhold` (Selection `withhold_pay` / `withhold` / `payment`,
  [account_payment.py:13](../../../../addons/l10n_account_withholding_tax/models/account_payment.py#L13)).
  Views, domains and chart data using the old names fail at install.
- **`account.tax.group` lost its settlement accounts** (`tax_payable_account_id`, `tax_receivable_account_id`,
  `advance_tax_payment_account_id`). They moved to `account.return.type`, company-dependent. Full notes:
  `documentations/account_returns.md`.
- **Core ships `l10n_ge`** and owns chart template `'ge'`. Chart-template functions are registered by
  *method name*, top of the MRO wins ([chart_template.py:78](../../../../addons/account/models/chart_template.py#L78)):
  a custom module that reuses a core name such as `_get_ge_res_company` silently replaces it. Extend a
  core chart with unique method names and `depends` on the l10n module; only define `@template('xx')`
  (model `template_data`) when you really create a new chart.
- **Installing** a module with `@template(code, model)` functions loads them into every existing company
  on that chart ([ir_module.py:72](../../../../addons/account/models/ir_module.py#L72): `_pre_reload_data`
  + `_load_data`). An upgrade (`-u`) does not. A backfill `post_init_hook` is redundant; records added in
  a later version still need a maintenance function or a chart reload.
- **No Georgian VAT return type.** Return types live in enterprise `l10n_xx_reports` modules (e.g.
  `l10n_at_reports/data/account_return_data.xml`). There is no `l10n_ge_reports`, and `account_reports`
  ships only the annual CIT and audit types (`account_return_data.xml`).
- **Account hierarchy is native**: `account.account` is `_parent_store` with `parent_id` and `active`
  (l10n CSVs load header accounts inactive), and the form and list already show Parent Account
  ([account_account_views.xml:72](../../../../addons/account/views/account_account_views.xml#L72)).
  The form has no `page[@name='Description']` any more.
- **Payment register pays only receivable/payable lines**: `account.payment._get_valid_payment_account_types()`
  returns `asset_receivable`, `liability_payable` ([account_payment.py:247](../../../../addons/account/models/account_payment.py#L247)).
  `l10n_ge`'s 310310 Salaries Payable is `liability_current` and 332010 Pension is not reconcilable, so
  payroll NET and pension legs on them cannot be paid through the register as shipped.

---

## 12. Unchanged — do not "fix" these

Still correct in v20, despite churn elsewhere:

- `models.Constraint(...)` / `models.Index(...)` / `models.UniqueIndex(...)` class attributes
  (`_sql_constraints` has 1 remaining occurrence in all of `addons/`)
- `@api.model_create_multi`, `@api.depends`, `@api.constrains`, `@api.ondelete`, `@api.onchange`
- `_compute_display_name()` (not `name_get()`)
- `<list>` (0 `<tree>` tags left in core views), `invisible="..."` expressions, `<chatter/>`
- `type='jsonrpc'` for JSON routes
- `odoo.Command`, `odoo.fields.Domain`, `bypass_search_access` (the v19 replacement for `auto_join`)
- `check_company=True`, `_check_company_auto`, `company_dependent=True`
- `self.env._("...")` as the preferred translation call
