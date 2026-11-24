# Security — Odoo 19

Two layers decide access: `ir.model.access` (may this group touch the model at all) and
`ir.rule` (which records). Both must pass. Read section 1 before writing any security file.

Source: [odoo/addons/base/models/ir_model.py:2095](../../../../odoo/addons/base/models/ir_model.py#L2095) (`ir.model.access`),
[odoo/addons/base/models/ir_rule.py:141](../../../../odoo/addons/base/models/ir_rule.py#L141) (`_compute_domain`),
[odoo/orm/models.py:4141](../../../../odoo/orm/models.py#L4141) (`_check_access`).

1. [ACLs and record rules](#1-acls-and-record-rules)
2. [Writing `ir.model.access.csv` and rules](#2-writing-irmodelaccesscsv-and-rules)
3. [Groups and privileges](#3-groups-and-privileges)
4. [Child models follow the parent](#4-child-models-follow-the-parent)
5. [Field-level security](#5-field-level-security)
6. [Programmatic access checks](#6-programmatic-access-checks)
7. [`sudo()` discipline](#7-sudo-discipline)
8. [Portal and public routes](#8-portal-and-public-routes)
9. [Raw SQL safety](#9-raw-sql-safety)
10. [CSRF and webhooks](#10-csrf-and-webhooks)
11. [Secrets and sensitive data](#11-secrets-and-sensitive-data)
12. [Vulnerability table](#12-vulnerability-table)

---

## 1. ACLs and record rules

| Layer | Record | Decides | Combination |
|---|---|---|---|
| ACL | `ir.model.access` row | CRUD on the model | **union** over the user's groups; an empty `group_id` grants **everyone**, portal and public included |
| global rule | `ir.rule` without `groups` | which records | **intersected**, applies to every user |
| group rule | `ir.rule` with `groups` | which records | **unioned** among the rules whose group the user has |

The ORM resolves the rules into one domain per operation —
[ir_rule.py:159-173](../../../../odoo/addons/base/models/ir_rule.py#L159):

```python
global_domains.append(Domain.OR(group_domains))
return Domain.AND(global_domains).optimize(model)
```

Consequences:

- **No ACL row → no access.** A new model with no `ir.model.access.csv` row is unusable by
  every non-superuser.
- **No rule → every record.** A model without `ir.rule` records is limited only by its ACLs.
- **Group rules only bind users in those groups.** A user in none of the rule groups is held
  only by the global rules. To widen access, add a group rule; never edit another module's rule.
- **Global rules cannot be escaped by adding a group.** Multi-company scoping lives there.

The evaluation context for `domain_force` is `user`, `company_id`, `company_ids` —
[ir_rule.py:38](../../../../odoo/addons/base/models/ir_rule.py#L38).

---

## 2. Writing `ir.model.access.csv` and rules

### ACLs

One file per module: `security/ir.model.access.csv`.

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_my_model_user,my.model user,model_my_model,group_my_module_user,1,1,1,0
access_my_model_manager,my.model manager,model_my_model,group_my_module_manager,1,1,1,1
access_my_model_line_user,my.model.line user,model_my_model_line,group_my_module_user,1,1,1,1
access_my_wizard,my.wizard,model_my_wizard,base.group_user,1,1,1,0
```

| Column | Value |
|---|---|
| `id` | XML id, unique in the module |
| `name` | human label |
| `model_id:id` | `model_` + model name with dots as underscores; another module's model: `sale.model_sale_order` |
| `group_id:id` | group XML id; empty grants **every** user, portal and public included — avoid |
| `perm_*` | `1` / `0` |

Read the real thing before writing your own —
[addons/purchase/security/ir.model.access.csv](../../../../addons/purchase/security/ir.model.access.csv).

### Record rules

In the groups file or a separate `security/<module>_rules.xml` —
[addons/sale/security/ir_rules.xml](../../../../addons/sale/security/ir_rules.xml).

```xml
<record id="my_model_comp_rule" model="ir.rule">
    <field name="name">My Model multi-company</field>
    <field name="model_id" ref="model_my_model"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>

<record id="my_model_own_records" model="ir.rule">
    <field name="name">My Model: own records only</field>
    <field name="model_id" ref="model_my_model"/>
    <field name="domain_force">[('user_id', '=', user.id)]</field>
    <field name="groups" eval="[(4, ref('group_my_module_user'))]"/>
</record>

<record id="my_model_see_all" model="ir.rule">
    <field name="name">My Model: all records</field>
    <field name="model_id" ref="model_my_model"/>
    <field name="domain_force">[(1, '=', 1)]</field>
    <field name="groups" eval="[(4, ref('group_my_module_manager'))]"/>
</record>

<record id="my_wizard_rule" model="ir.rule">
    <field name="name">My Wizard: own wizards only</field>
    <field name="model_id" ref="model_my_wizard"/>
    <field name="domain_force">[('create_uid', '=', user.id)]</field>
</record>
```

- The manager rule is needed: without it, a manager (who implies User) is held by the
  user's own-records rule
- `perm_read` / `perm_write` / `perm_create` / `perm_unlink` on a rule (all default `True`)
  limit the operations it applies to — `sale_order_rule_portal` in sale's `ir_rules.xml`
- Wizards scoped to their creator: `sale_advance_payment_inv_rule`
  ([ir_rules.xml:175](../../../../addons/sale/security/ir_rules.xml#L175))

### Manifest placement

```python
'data': [
    'security/my_module_security.xml',   # groups (+ rules) — FIRST
    'security/ir.model.access.csv',      # ACLs — right after the groups
    'data/...', 'report/...', 'wizard/...', 'views/...', 'views/menus.xml',
],
```

Verified in `account`, `stock`, `hr`, `purchase`, `project`: the groups file is entry 0 and
`ir.model.access.csv` entry 1. The CSV references the groups, so the groups file loads first.

---

## 3. Groups and privileges

File: `security/<module>_security.xml`, first in `data`. Three levels:
`ir.module.category` ▶ `res.groups.privilege` ▶ `res.groups`.

```xml
<odoo>
<data>
    <record model="res.groups.privilege" id="res_groups_privilege_my_module">
        <field name="name">My Module</field>
        <field name="sequence">20</field>
        <field name="category_id" ref="base.module_category_supply_chain"/>
    </record>

    <record id="group_my_module_user" model="res.groups">
        <field name="name">User</field>
        <field name="sequence">10</field>
        <field name="privilege_id" ref="res_groups_privilege_my_module"/>
        <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
    </record>

    <record id="group_my_module_manager" model="res.groups">
        <field name="name">Administrator</field>
        <field name="sequence">20</field>
        <field name="privilege_id" ref="res_groups_privilege_my_module"/>
        <field name="implied_ids" eval="[(4, ref('group_my_module_user'))]"/>
        <field name="user_ids" eval="[(4, ref('base.user_root')), (4, ref('base.user_admin'))]"/>
    </record>
</data>
</odoo>
```

Pattern copied from
[addons/purchase/security/purchase_security.xml](../../../../addons/purchase/security/purchase_security.xml).
Pick `category_id` from [base/data/ir_module_category_data.xml](../../../../odoo/addons/base/data/ir_module_category_data.xml).

- `res.groups` has no `category_id` — it has `privilege_id`
- `user_ids`, not `users`; `group_ids`, not `groups_id`, on `ir.actions.*`
- Manager implies User; never restate a permission a group already implies
- A group with no privilege is a plain feature flag (e.g. `group_warning_purchase`)
- `res.groups.model_access` lists the group's ACLs, `rule_groups` its rules
  ([res_groups.py:24](../../../../odoo/addons/base/models/res_groups.py#L24))

---

## 4. Child models follow the parent

A line or detail model whose visibility should follow its parent repeats the parent's
domain through the many2one, and carries its own company rule when it has `company_id`:

```xml
<record id="sale_order_line_rule_portal" model="ir.rule">
    <field name="name">Portal Sales Orders Line</field>
    <field name="model_id" ref="sale.model_sale_order_line"/>
    <field name="domain_force">[('order_id.partner_id','child_of',[user.commercial_partner_id.id])]</field>
    <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
</record>
```

[addons/sale/security/ir_rules.xml:35](../../../../addons/sale/security/ir_rules.xml#L35). When the parent's
rule changes, change the child's in the same commit — nothing keeps them in sync.

---

## 5. Field-level security

```python
internal_cost = fields.Monetary(
    string="Internal Cost",
    currency_field='currency_id',
    groups='my_module.group_my_module_manager',
)
```

```xml
<field name="internal_cost" groups="my_module.group_my_module_manager"/>
```

A `groups=` field is stripped from reads, writes, exports and the web client for users
outside the group — enforced by `_check_field_access()` /
`_has_field_access()`, [models.py:3375](../../../../odoo/orm/models.py#L3375). Put it on the
field first; the view attribute alone only hides it in the UI.

**Fields only the module may write** (a status, an external id, downloaded files) cannot use `groups=` when users
must read them, and `readonly=True` is not enforced on the server. Refuse them in `create`/`write` unless
`self.env.su` — and in `create` also pin explicit values, because defaults are merged **after** the override:
a `default_<field>` context key or a personal `ir.default` row (every internal user may create one) fills the field
otherwise ([models.py:1289-1294, 1600, 4800-4802](../../../../odoo/orm/models.py#L1289)). A pinned key can still be
dropped by a lower `base` override (a field guard), and `ir.default` is read per `env.uid` even under `sudo()`: for a
field nobody may default (a technical link), pop it in `default_get` for every environment instead. Core counts a
`default_<field>` context key as a value the user sends and checks it like one (models.py:4648-4659):

```python
if not self.env.su:
    if any(SYNC_FIELDS.intersection(vals) for vals in vals_list):
        raise AccessError(self.env._("..."))
    vals_list = [dict.fromkeys(SYNC_FIELDS, False) | {'state': 'draft'} | vals for vals in vals_list]
```

The same blind spot hits any **check written against `vals` in a `create` override** (e.g. "the linked record must
be readable"): a default fills the field after the check. Do **not** move an access check into `@api.constrains`:
Odoo runs every constraint on `self.sudo()` ([models.py:1260-1262](../../../../odoo/orm/models.py#L1260)), so
`has_access` is always True there. Check the created records instead, after `super().create()` (and after
`super().write()` when the field is in vals), in the caller's env — the value then includes defaults, and a caller's
own `sudo()` still passes.

---

## 6. Programmatic access checks

```python
records.check_access('read')            # raises AccessError
if records.has_access('write'): ...     # bool
allowed = records._filtered_access('unlink')   # the subset the user may touch
self.env['my.model'].browse().check_access('create')   # model-level check

model._check_field_access(model._fields['cost'], 'write')  # raises
model._has_field_access(model._fields['cost'], 'read')     # bool
```

- operations: `'read'`, `'write'`, `'create'`, `'unlink'`
- all of them short-circuit to "allowed" under `sudo()` / `env.su` — call them on the
  **non-sudoed** recordset
- `create()` / `write()` / `unlink()` already call `check_access` internally; only re-check
  when you bypass the ORM or wrap something in `sudo()`
- `self.env['ir.rule']._compute_domain(model_name, op)` returns the resolved rule domain —
  useful for debugging why a record is invisible
- deprecated since 18.0, still working in 19: `check_access_rights` → `check_access` /
  `has_access`, `check_access_rule` → `check_access`, `_filter_access_rules` →
  `_filtered_access` ([models.py:4168-4199](../../../../odoo/orm/models.py#L4168));
  `check_field_access_rights` → `_check_field_access`, deprecated since 19.0
  ([models.py:3439](../../../../odoo/orm/models.py#L3439))

---

## 7. `sudo()` discipline

Order of operations, every time:

```python
def action_generate_invoice(self):
    self.ensure_one()
    # 1. permission: is this user allowed to trigger the action at all?
    if not self.env.user.has_group('sale.group_sale_salesman'):
        raise AccessError(self.env._("Only salespersons can generate invoices."))
    # 2. business state, before any sudo
    if self.state != 'sale':
        raise UserError(self.env._("Only confirmed orders can be invoiced."))
    # 3. prepare values with the user's own rights
    invoice_vals = self._prepare_invoice()
    # 4. sudo only for the step that needs it, with the reason on one line
    # sudo: sale users have no create access on account.move
    return self.env['account.move'].sudo().create(invoice_vals)
```

Never:

```python
records = self.sudo().search([])                      # silencing an access error
self.sudo().write({'field': value_from_request})      # unvalidated user input
self.sudo().search([('company_id', '!=', self.env.company.id)])   # cross-company leak
```

`sudo()` bypasses ACLs and record rules completely, which means it also bypasses every
multi-company rule. Any `sudo()` on a company-scoped model
must re-add the company filter by hand.

---

## 8. Portal and public routes

```python
class MyPortal(CustomerPortal):

    @http.route('/my/records/<int:record_id>', type='http', auth='user', website=True)
    def portal_record(self, record_id, **kw):
        record = request.env['my.model'].sudo().browse(record_id)
        if not record.exists() or record.partner_id != request.env.user.partner_id:
            raise request.not_found()      # 404, not 403 — do not confirm the id exists
        return request.render('my_module.portal_record', {'record': record})
```

- filter by `partner_id` (or `commercial_partner_id`) yourself — never trust the URL id
- 404 on mismatch, so ids cannot be enumerated
- `sudo()` here is justified *because* of the explicit ownership filter above it — say so
- never expose cost, margin, internal notes or other staff-only fields in portal templates
- portal access is an ACL row for `base.group_portal` plus a portal `ir.rule`, e.g.
  `[('partner_id','child_of',[user.commercial_partner_id.id])]` (`sale_order_rule_portal`)

---

## 9. Raw SQL safety

Raw SQL bypasses ACLs and record rules entirely — there is no company rule either. Use the ORM for business CRUD; use SQL only for reporting shapes the ORM
cannot express, and re-apply the security filter yourself.

```python
self.env.cr.execute("""
    SELECT p.id, COUNT(o.id) AS order_count, SUM(o.amount_total) AS total
      FROM res_partner p
      LEFT JOIN sale_order o ON o.partner_id = p.id
     WHERE o.company_id IN %s
       AND o.state IN %s
       AND o.date_order >= %s
     GROUP BY p.id
""", (tuple(self.env.companies.ids), ('sale',), date_from))
rows = self.env.cr.dictfetchall()
```

Never build SQL with `f""`, `%`-formatting or `+`. Prefer `odoo.tools.SQL` for composed
queries — it is injection-safe by construction.

---

## 10. CSRF and webhooks

- `type='http'` POST routes are CSRF-checked automatically; QWeb forms include the token
- `type='jsonrpc'` uses session auth and is not CSRF-relevant
- `csrf=False` is only for endpoints that must accept external callers, and it must be
  paired with a real authentication step:

```python
# Use auth='public' when reading request.env (auth='none' has no DB/env!)
@http.route('/my/webhook', type='http', auth='public', csrf=False, methods=['POST'])
def webhook(self, **post):
    if not expected_signature or not hmac.compare_digest(post.get('signature', ''), expected_signature):
        raise Forbidden()
```

Use `hmac.compare_digest` for every secret comparison — `==` leaks timing.

---

## 11. Secrets and sensitive data

```python
# never in a data file
<field name="value">sk_live_abc123</field>

# ship it empty, let the admin fill it
<field name="value"></field>

api_key = self.env['ir.config_parameter'].sudo().get_param('my_module.api_key')
if not api_key:
    raise UserError(self.env._("API key not configured (Settings > Technical > Parameters)."))
```

- never log a password, token or key — `_logger.info("calling %s", url)` is fine
- token fields carry `groups='base.group_system'` and `copy=False`
- `ir.config_parameter` reads need `sudo()`; that is expected and does not need a comment

---

## 12. Vulnerability table

| Vulnerability | Shape | Fix |
|---|---|---|
| SQL injection | `execute(f"... {value}")` | `%s` parameters or `tools.SQL` |
| Missing ACL | new model, no `ir.model.access.csv` row | nobody can use it — add the row |
| Over-broad ACL | empty `group_id:id` | grants every user, portal and public included — name a group |
| IDOR | `browse(id_from_url)` with no ownership check | ownership filter + `check_access('read')` + 404 |
| Broken access via sudo | `sudo()` before validating the user | permission check → state check → `sudo()` |
| Cross-company leak | no global company rule, or `sudo()` on a scoped model | company `ir.rule` + re-filter under `sudo()` |
| XSS in QWeb | `t-out` on raw HTML from users | escape, or sanitize the stored HTML |
| Stored XSS via SVG | SVG upload | `Binary`/`Image` block SVG for non-admins — keep it |
| Mass assignment | `write(request.params)` | whitelist the fields |
| Path traversal | user-controlled file path | validate against a fixed root |
| Open redirect | redirect to a user-supplied URL | allow only internal targets |
| Timing attack | `token == expected` | `hmac.compare_digest` |
