# Security Deep-Dive — Odoo 19+

## Table of Contents

1. [Security Layers Overview](#1-security-layers)
2. [Security Groups](#2-security-groups)
3. [Access Control Lists (ACLs)](#3-acls)
4. [Record Rules](#4-record-rules)
5. [Field-Level Security](#5-field-level-security)
6. [sudo() Best Practices](#6-sudo-best-practices)
7. [Raw SQL Safety](#7-raw-sql-safety)
8. [Controller Security](#8-controller-security)
9. [Multi-Company Security](#9-multi-company-security)
10. [Common Vulnerabilities](#10-common-vulnerabilities)
11. [Portal User Security](#11-portal-user-security)
12. [CSRF Protection](#12-csrf-protection)
13. [@api.ondelete](#13-apiondelete)
14. [Data File Security](#14-data-file-security)
15. [Sensitive Data Handling](#15-sensitive-data-handling)

---

## 1. Security Layers

Odoo security works in layers. All layers must pass for access to be granted:

```
User Request
    ↓
[1] Security Groups — Does the user belong to a group that has access?
    ↓
[2] Access Rights (ACLs) — Can this group CRUD this model?
    ↓
[3] Record Rules — Can this user access THIS specific record?
    ↓
[4] Field Access — Can this user see/edit THIS specific field?
    ↓
Access Granted
```

---

## 2. Security Groups

### Template: `security/groups.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Module category -->
    <record id="module_category_my_module" model="ir.module.category">
        <field name="name">My Module</field>
        <field name="description">Manage my module operations</field>
        <field name="sequence">20</field>
    </record>

    <!-- User group -->
    <record id="group_my_module_user" model="res.groups">
        <field name="name">User</field>
        <field name="category_id" ref="module_category_my_module"/>
        <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
    </record>

    <!-- Manager group (inherits User) -->
    <record id="group_my_module_manager" model="res.groups">
        <field name="name">Manager</field>
        <field name="category_id" ref="module_category_my_module"/>
        <field name="implied_ids" eval="[(4, ref('group_my_module_user'))]"/>
        <field name="users" eval="[(4, ref('base.user_root')), (4, ref('base.user_admin'))]"/>
    </record>
</odoo>
```

**Rules:**
- Manager always implies User
- Admin/root users should be in Manager group by default
- Use `implied_ids` to create group hierarchy (never duplicate permissions)

---

## 3. Access Control Lists (ACLs)

### Template: `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_my_model_user,my.model.user,model_my_model,group_my_module_user,1,1,1,0
access_my_model_manager,my.model.manager,model_my_model,group_my_module_manager,1,1,1,1
access_my_model_line_user,my.model.line.user,model_my_model_line,group_my_module_user,1,1,1,1
```

**Rules:**
- One entry per model per group — use unique `id` values
- Users typically cannot unlink (delete) — only managers
- Every model MUST have at least one ACL entry
- `model_id:id` uses `model_` prefix + model name with dots → underscores
- Empty `group_id:id` = applies to ALL users (including portal) — use with extreme caution

---

## 4. Record Rules

### Template: `security/rules.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Multi-company rule (ALWAYS include for multi-company models) -->
    <record id="rule_my_model_company" model="ir.rule">
        <field name="name">My Model: Multi-Company</field>
        <field name="model_id" ref="model_my_model"/>
        <field name="domain_force">
            ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
        </field>
    </record>

    <!-- User sees own records only -->
    <record id="rule_my_model_user" model="ir.rule">
        <field name="name">My Model: User Own Records</field>
        <field name="model_id" ref="model_my_model"/>
        <field name="domain_force">
            [('user_id', '=', user.id)]
        </field>
        <field name="groups" eval="[(4, ref('group_my_module_user'))]"/>
    </record>

    <!-- Manager sees all records (empty domain = allow all) -->
    <record id="rule_my_model_manager" model="ir.rule">
        <field name="name">My Model: Manager All Records</field>
        <field name="model_id" ref="model_my_model"/>
        <field name="domain_force">[(1, '=', 1)]</field>
        <field name="groups" eval="[(4, ref('group_my_module_manager'))]"/>
    </record>
</odoo>
```

**Important rules:**
- Global rules (no `groups`) are **intersected** (all must pass)
- Group rules are **unioned** (any matching rule grants access)
- Multi-company rules should always be **global** (no groups)
- `company_ids` = all companies the user has access to (list)
- `company_id` = user's currently selected company (single id)

---

## 5. Field-Level Security

```python
# Restrict field visibility to specific groups
secret_notes = fields.Text(
    string='Secret Notes',
    groups='my_module.group_my_module_manager',
)
```

In XML views:
```xml
<field name="internal_cost" groups="my_module.group_my_module_manager"/>
```

---

## 6. sudo() Best Practices

### When sudo() is justified:
- Creating records in models the user doesn't have write access to (e.g., creating an invoice from a sale order)
- Reading configuration that's not accessible to the current user
- System operations in cron jobs

### Mandatory pattern:

```python
def action_generate_invoice(self):
    """Generate invoice for confirmed orders.

    Uses sudo() for invoice creation because sale users may not have
    direct write access to account.move. User's permission to trigger
    this action is verified by group check.
    """
    self.ensure_one()
    # Step 1: Validate current user has the right
    if not self.env.user.has_group('sale.group_sale_salesman'):
        raise AccessError(_("Only salespersons can generate invoices."))
    # Step 2: Validate business logic BEFORE sudo
    if self.state != 'confirmed':
        raise UserError(_("Only confirmed orders can be invoiced."))
    # Step 3: Prepare values WITHOUT sudo (use current user's access)
    invoice_vals = self._prepare_invoice_values()
    # Step 4: Create with sudo, with clear comment
    # sudo() needed: sale user has no write access to account.move
    invoice = self.env['account.move'].sudo().create(invoice_vals)
    return invoice
```

### sudo() anti-patterns to AVOID:

```python
# NEVER: sudo() to silence access errors without understanding why
records = self.sudo().search([])

# NEVER: sudo() on user input without validation
self.sudo().write({'field': user_provided_value})

# NEVER: sudo() that exposes cross-company data
other_company_records = self.sudo().search([('company_id', '!=', self.env.company.id)])
```

---

## 7. Raw SQL Safety

**Rule: Never use raw SQL when the ORM can do the job.**

When raw SQL is unavoidable:

```python
def _get_complex_report_data(self):
    """Fetch report data using raw SQL for complex aggregation.

    Raw SQL justified: The required LATERAL JOIN and window functions
    cannot be expressed via the ORM.
    """
    # ALWAYS use parameterized queries
    self.env.cr.execute("""
        SELECT
            p.id,
            p.name,
            COUNT(o.id) AS order_count,
            SUM(o.amount_total) AS total_amount
        FROM res_partner p
        LEFT JOIN sale_order o ON o.partner_id = p.id
        WHERE p.company_id = %s
            AND o.state IN %s
            AND o.date_order >= %s
        GROUP BY p.id, p.name
        HAVING SUM(o.amount_total) > %s
    """, (
        self.env.company.id,
        tuple(['sale', 'done']),
        fields.Date.today() - timedelta(days=365),
        1000.0,
    ))
    return self.env.cr.dictfetchall()
```

**NEVER:**
```python
# SQL injection — CRITICAL vulnerability
self.env.cr.execute(f"SELECT * FROM res_partner WHERE name = '{name}'")
self.env.cr.execute("SELECT * FROM res_partner WHERE name = '%s'" % name)
self.env.cr.execute("SELECT * FROM res_partner WHERE name = " + name)
```

---

## 8. Controller Security

```python
from odoo import http
from odoo.http import request

class MyController(http.Controller):

    @http.route('/my_module/data', type='jsonrpc', auth='user', methods=['POST'])
    def get_data(self, **kwargs):
        """Fetch data for authenticated users only.

        Auth types:
          - 'user': Requires login (internal users)
          - 'public': No login required
          - 'none': No auth, no env — use for health checks only
        """
        # Always validate input
        record_id = kwargs.get('record_id')
        if not record_id or not isinstance(record_id, int):
            raise ValueError("Invalid record ID")

        # Access through ORM respects security rules
        record = request.env['my.model'].browse(record_id)
        record.check_access('read')  # v19: explicit access check

        return {'name': record.name, 'state': record.state}
```

**Note:** In v19, `type='json'` is a deprecated alias of `type='jsonrpc'`.
Use `type='jsonrpc'` in new code.

---

## 9. Multi-Company Security

```python
class MyModel(models.Model):
    """Multi-company aware model."""

    _name = 'my.model'
    _description = 'My Model'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # The ORM enforces company consistency automatically when check_company=True
    partner_id = fields.Many2one('res.partner', check_company=True)
```

---

## 10. Common Vulnerabilities

| Vulnerability | Example | Fix |
|--------------|---------|-----|
| SQL Injection | `execute(f"... {user_input}")` | Always use `%s` params |
| Broken Access | Public method calls `sudo()` | Validate group before sudo |
| IDOR | `browse(user_provided_id)` without check | Call `check_access('read')` |
| XSS in QWeb | `t-raw` with user input | Use `t-esc` or sanitize |
| Mass Assignment | `write(request.params)` | Whitelist allowed fields |
| Cross-Company Leak | Missing company record rule | Always add company rule |
| Path Traversal | User-controlled file path | Validate / sanitize paths |
| Open Redirect | Redirect to user URL | Validate redirect target is internal |
| Timing Attack | String `==` for secrets | Use `hmac.compare_digest()` |

---

## 11. Portal User Security

Portal users have minimal permissions. Extra care is needed when exposing
data to them.

### Portal record rules:
```xml
<!-- Portal user can only see their own records -->
<record id="rule_my_model_portal" model="ir.rule">
    <field name="name">My Model: Portal Own Records</field>
    <field name="model_id" ref="model_my_model"/>
    <field name="domain_force">
        [('partner_id', '=', user.partner_id.id)]
    </field>
    <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
</record>
```

### Portal controller pattern:
```python
from odoo.addons.portal.controllers.portal import CustomerPortal

class MyPortal(CustomerPortal):
    """Portal controller for my module."""

    @http.route('/my/records', type='http', auth='user', website=True)
    def portal_my_records(self, **kwargs):
        """Display portal user's records.

        Auth type 'user' ensures login is required.
        Always filter by partner to prevent IDOR.
        """
        partner = request.env.user.partner_id
        records = request.env['my.model'].sudo().search([
            ('partner_id', '=', partner.id),
        ])
        # sudo() justified: portal user has no ACL on my.model,
        # but we pre-filter by their partner_id above
        return request.render('my_module.portal_records', {
            'records': records,
        })

    @http.route('/my/records/<int:record_id>', type='http', auth='user', website=True)
    def portal_my_record_detail(self, record_id, **kwargs):
        """Display a single record detail for portal user.

        CRITICAL: Must verify the record belongs to the logged-in user.
        """
        record = request.env['my.model'].sudo().browse(record_id)
        if not record.exists():
            raise request.not_found()
        # IDOR prevention: verify ownership
        if record.partner_id != request.env.user.partner_id:
            raise request.not_found()  # 404 instead of 403 to avoid info leak
        return request.render('my_module.portal_record_detail', {
            'record': record,
        })
```

**Portal rules:**
- ALWAYS filter by `partner_id` — never trust the URL parameter alone
- Return 404 (not 403) for records that don't belong to the user (prevents enumeration)
- Use `sudo()` with partner filter — portal users have no direct ACL on most models
- Never expose internal fields (cost, margin, notes) in portal templates

---

## 12. CSRF Protection

Odoo has built-in CSRF protection for HTTP controllers. Understand when
it's active and when you might accidentally bypass it.

```python
# SAFE — CSRF token is automatically included in forms rendered by QWeb
@http.route('/my/submit', type='http', auth='user', methods=['POST'], website=True)
def submit_form(self, **post):
    """Handle form submission with automatic CSRF validation."""
    # Odoo validates the csrf_token automatically for type='http' POST
    ...

# SAFE — JSON-RPC calls don't need CSRF (they use session auth)
@http.route('/my/api', type='jsonrpc', auth='user', methods=['POST'])
def api_call(self, **kwargs):
    """API endpoint — CSRF not applicable for JSON-RPC."""
    ...

# DANGEROUS — explicitly disabling CSRF
@http.route('/my/webhook', type='http', auth='none', csrf=False, methods=['POST'])
def webhook_receiver(self, **post):
    """Receive external webhook — CSRF disabled.

    WARNING: csrf=False means anyone can POST to this endpoint.
    Always validate the request using a shared secret or signature.
    """
    secret = post.get('secret')
    if not hmac.compare_digest(secret or '', WEBHOOK_SECRET):
        raise Forbidden()
    ...
```

**CSRF rules:**
- Never use `csrf=False` unless the endpoint must accept external webhooks
- When `csrf=False`, authenticate the request another way (API key, HMAC signature)
- Use `hmac.compare_digest()` for timing-safe secret comparison
- QWeb templates automatically include `csrf_token` in forms — don't remove it

---

## 13. @api.ondelete

Modern Odoo (v16+) provides `@api.ondelete` as the preferred way to restrict
record deletion. See SKILL.md section 2.3 for details and examples.

Key security aspect: `@api.ondelete` runs BEFORE cascade deletes on related
records, so it catches violations that `unlink()` overrides might miss.

---

## 14. Data File Security

### Sensitive data in XML data files:
```xml
<!-- NEVER hardcode secrets in data files -->
<!-- BAD -->
<record id="my_config" model="ir.config_parameter">
    <field name="key">my_module.api_key</field>
    <field name="value">sk_live_abc123</field>  <!-- NEVER -->
</record>

<!-- GOOD — set empty, let admin configure via UI -->
<record id="my_config" model="ir.config_parameter">
    <field name="key">my_module.api_key</field>
    <field name="value"></field>
</record>
```

### Protecting config parameters:
```python
# Reading config parameters safely
api_key = self.env['ir.config_parameter'].sudo().get_param(
    'my_module.api_key', default=''
)
if not api_key:
    raise UserError(_("API key not configured. Go to Settings > Technical > Parameters."))
```

---

## 15. Sensitive Data Handling

```python
# NEVER log sensitive data
_logger.info("API key: %s", api_key)  # FORBIDDEN
_logger.info("Password: %s", password)  # FORBIDDEN
_logger.info("API call made to %s", url)  # OK — no secrets

# NEVER store plaintext passwords
# Use Odoo's built-in hashing for custom auth:
from odoo.addons.base.models.res_users import check_identity

# For API tokens, use ir.config_parameter (encrypted at rest in some deployments)
# or fields with groups restriction:
api_token = fields.Char(
    string='API Token',
    groups='base.group_system',  # only admin can see
    copy=False,
)
```
