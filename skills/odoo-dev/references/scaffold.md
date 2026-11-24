# Module Scaffold — Odoo 19

Copy-paste templates for a new Odoo 19 module. Delete every part the task does not need — an unused
wizard, controller, or demo file is a cost, not a courtesy.

The code below follows our rules: compact layout (`compact-code.md`), a one-line docstring only
where it carries a why, multi-company by default, `self.env._()` for user text, and
`security/ir.model.access.csv` + XML `ir.rule` for security.

---

## Layout

Only create the folders you actually use.

```
my_module/
├── __init__.py
├── __manifest__.py
├── data/
│   └── ir_sequence_data.xml
├── models/
│   ├── __init__.py
│   └── my_model.py
├── security/
│   ├── my_module_security.xml        # groups, privilege, record rules — FIRST in manifest
│   └── ir.model.access.csv           # ACLs — right after the groups file
├── static/description/icon.png       # 128x128 or 256x256
├── views/
│   ├── my_model_views.xml
│   └── my_model_menus.xml
└── wizard/                           # only if there is a wizard (singular, matches core)
    ├── __init__.py
    ├── my_wizard.py
    └── my_wizard_views.xml
```

Add `controllers/`, `report/`, `tests/`, `demo/`, `static/src/` only when the task needs them.

---

## `__manifest__.py`

```python
{
    'name': "MODULE_TITLE",
    'version': '19.0.1.0.0',
    'category': 'CATEGORY',
    'summary': "SHORT_SUMMARY",
    'description': """
PLAIN_TEXT_DESCRIPTION — two or three sentences, no Markdown.
Full documentation: README.md and README_DEV.md in the module directory.
""",
    'author': "ORGANIZATION_NAME",
    'license': 'LGPL-3',
    'depends': ['mail', 'product'],
    'data': [
        'security/my_module_security.xml',   # groups & record rules first
        'security/ir.model.access.csv',      # ACLs right after groups
        'data/ir_sequence_data.xml',
        'views/my_model_views.xml',
        'views/my_model_menus.xml',          # menus after the actions they reference
    ],
    'installable': True,
    'application': True,
}
```

- `name`, `author`, and `license` are mandatory in Odoo 19 (`odoo/modules/module.py`).
- Never use a `20.0.*` version prefix (uninstallable on Odoo 19). Do not bump `version` on existing modules unless asked.
- Always set `description` (plain text, no Markdown). Without `description` and without `static/description/index.html`, Odoo parses `README.md` as reStructuredText (`odoo/addons/base/models/ir_module.py`), logging docutils errors on every update.
- Depend on the smallest modules whose features you actually use (here `mail` and `product`; `base` is implicit).
- `'application': True` only if the module deserves its own Apps tile.

---

## `models/my_model.py`

```python
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MyModel(models.Model):
    _name = 'my.module.model'
    _description = "My Model"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, readonly=True, default="New")
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', "Draft"),
        ('confirmed', "Confirmed"),
        ('done', "Done"),
        ('cancel', "Cancelled"),
    ], required=True, default='draft', copy=False, tracking=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    user_id = fields.Many2one('res.users', string="Responsible", default=lambda self: self.env.user, tracking=True)
    partner_id = fields.Many2one('res.partner', string="Partner", check_company=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='restrict', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    line_ids = fields.One2many('my.module.model.line', 'order_id', string="Lines")
    amount_total = fields.Monetary(compute='_compute_amount_total', store=True)

    _positive_amount = models.Constraint("CHECK (amount_total >= 0)", "The total cannot be negative.")

    @api.depends('line_ids.price_total')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = sum(record.line_ids.mapped('price_total'))

    @api.constrains('date')
    def _check_date(self):
        """Refuse a past date while draft; confirmed records keep their original date."""
        today = fields.Date.context_today(self)
        for record in self.filtered(lambda r: r.state == 'draft'):
            if record.date < today:
                raise ValidationError(self.env._("The date cannot be in the past."))

    @api.model_create_multi
    def create(self, vals_list):
        """Number new records from their own company's sequence, never another company's."""
        for vals in vals_list:
            if vals.get('name', "New") == "New":
                company_id = vals.get('company_id') or self.env.company.id
                vals['name'] = self.env['ir.sequence'].with_company(company_id).next_by_code('my.module.model') or "New"
        return super().create(vals_list)

    def copy_data(self, default=None):
        """Suffix duplicates with "(copy)" so they are not mistaken for the original."""
        vals_list = super().copy_data(default=default)
        for record, vals in zip(self, vals_list):
            vals['name'] = self.env._("%s (copy)", record.name)
        return vals_list

    def action_confirm(self):
        """Confirm draft records all-or-nothing, naming every invalid record."""
        if invalid := self.filtered(lambda r: r.state != 'draft'):
            raise UserError(self.env._("Only draft records can be confirmed: %s", invalid.mapped('name')))
        self.state = 'confirmed'

    def action_done(self):
        """Mark confirmed records done all-or-nothing."""
        if invalid := self.filtered(lambda r: r.state != 'confirmed'):
            raise UserError(self.env._("Only confirmed records can be marked done: %s", invalid.mapped('name')))
        self.state = 'done'

    def action_cancel(self):
        self.state = 'cancel'

    def action_draft(self):
        self.state = 'draft'


class MyModelLine(models.Model):
    _name = 'my.module.model.line'
    _description = "My Model Line"
    _order = 'order_id, sequence, id'
    _check_company_auto = True

    order_id = fields.Many2one('my.module.model', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='order_id.currency_id')
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Description", required=True)
    product_id = fields.Many2one('product.product', check_company=True)
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Monetary()
    price_total = fields.Monetary(compute='_compute_price_total', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_price_total(self):
        for line in self:
            line.price_total = line.quantity * line.price_unit
```

Notes on the choices above:
- Action methods act on the whole recordset, pass the list directly to `self.env._("%s", invalid.mapped('name'))`, and raise once.
- `fields.Date.context_today` uses the user's timezone (never UTC `fields.Date.today` for business dates).
- `copy_data()`, not `copy()`, so batch duplication works cleanly.
- Both `MyModel` and `MyModelLine` set `_check_company_auto = True` because both declare `check_company=True` fields.
- `_order` always ends on unique `id` so pagination is deterministic.

---

## `security/my_module_security.xml`

```xml
<odoo>
    <record id="res_groups_privilege_my_module" model="res.groups.privilege">
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

    <record id="my_model_comp_rule" model="ir.rule">
        <field name="name">My Model multi-company</field>
        <field name="model_id" ref="model_my_module_model"/>
        <field name="domain_force">[('company_id', 'in', company_ids)]</field>
    </record>

    <record id="my_model_line_comp_rule" model="ir.rule">
        <field name="name">My Model Line multi-company</field>
        <field name="model_id" ref="model_my_module_model_line"/>
        <field name="domain_force">[('company_id', 'in', company_ids)]</field>
    </record>

    <record id="my_model_user_own" model="ir.rule">
        <field name="name">My Model: own or unassigned</field>
        <field name="model_id" ref="model_my_module_model"/>
        <field name="domain_force">['|', ('user_id', '=', user.id), ('user_id', '=', False)]</field>
        <field name="groups" eval="[(4, ref('group_my_module_user'))]"/>
    </record>

    <record id="my_model_see_all" model="ir.rule">
        <field name="name">My Model: all records</field>
        <field name="model_id" ref="model_my_module_model"/>
        <field name="domain_force">[(1, '=', 1)]</field>
        <field name="groups" eval="[(4, ref('group_my_module_manager'))]"/>
    </record>
</odoo>
```

Pick `category_id` from `odoo/addons/base/data/ir_module_category_data.xml`.

---

## `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_my_model_user,my.module.model user,model_my_module_model,group_my_module_user,1,1,1,0
access_my_model_manager,my.module.model manager,model_my_module_model,group_my_module_manager,1,1,1,1
access_my_model_line_user,my.module.model.line user,model_my_module_model_line,group_my_module_user,1,1,1,1
```

The manager `[(1, '=', 1)]` rule is needed because `group_my_module_manager` implies `group_my_module_user`, so without it the own-or-unassigned rule would bind managers too. Company rules have no `groups` (global, AND-ed onto every user). Never leave `group_id:id` empty in `ir.model.access.csv` (that grants to every user including portal/public). Full rules: `security.md`.

---

## `data/ir_sequence_data.xml`

```xml
<odoo noupdate="1">
    <record id="seq_my_module_model" model="ir.sequence">
        <field name="name">My Model</field>
        <field name="code">my.module.model</field>
        <field name="prefix">MM/%(year)s/</field>
        <field name="padding">5</field>
        <field name="company_id" eval="False"/>
    </record>
</odoo>
```

`noupdate="1"` on `<odoo>` preserves user prefix customizations across upgrades.

---

## `views/my_model_views.xml`

```xml
<odoo>
    <record id="my_model_view_form" model="ir.ui.view">
        <field name="name">my.module.model.view.form</field>
        <field name="model">my.module.model</field>
        <field name="arch" type="xml">
            <form>
                <header>
                    <button name="action_confirm" type="object" string="Confirm"
                            class="oe_highlight" invisible="state != 'draft'"/>
                    <button name="action_done" type="object" string="Done"
                            class="oe_highlight" invisible="state != 'confirmed'"/>
                    <button name="action_cancel" type="object" string="Cancel"
                            invisible="state in ('done', 'cancel')"/>
                    <button name="action_draft" type="object" string="Reset to Draft"
                            invisible="state != 'cancel'"/>
                    <field name="state" widget="statusbar" statusbar_visible="draft,confirmed,done"/>
                </header>
                <sheet>
                    <div class="oe_title">
                        <h1><field name="name" readonly="1"/></h1>
                    </div>
                    <group>
                        <group>
                            <field name="partner_id"/>
                            <field name="user_id"/>
                            <field name="date"/>
                        </group>
                        <group>
                            <field name="company_id" groups="base.group_multi_company"/>
                            <field name="currency_id" invisible="1"/>
                        </group>
                    </group>
                    <notebook>
                        <page string="Lines" name="lines">
                            <field name="line_ids">
                                <list editable="bottom">
                                    <field name="sequence" widget="handle"/>
                                    <field name="product_id"/>
                                    <field name="name"/>
                                    <field name="quantity"/>
                                    <field name="price_unit"/>
                                    <field name="price_total"/>
                                    <field name="currency_id" column_invisible="1"/>
                                </list>
                            </field>
                        </page>
                    </notebook>
                    <group class="oe_subtotal_footer">
                        <field name="amount_total"/>
                    </group>
                </sheet>
                <chatter/>
            </form>
        </field>
    </record>

    <record id="my_model_view_list" model="ir.ui.view">
        <field name="name">my.module.model.view.list</field>
        <field name="model">my.module.model</field>
        <field name="arch" type="xml">
            <list multi_edit="1">
                <field name="name" decoration-bf="1"/>
                <field name="partner_id"/>
                <field name="user_id"/>
                <field name="date"/>
                <field name="amount_total" sum="Total"/>
                <field name="currency_id" column_invisible="1"/>
                <field name="company_id" groups="base.group_multi_company" optional="show"/>
                <field name="state" widget="badge"
                       decoration-success="state == 'done'"
                       decoration-info="state == 'confirmed'"
                       decoration-muted="state == 'cancel'"/>
            </list>
        </field>
    </record>

    <record id="my_model_view_search" model="ir.ui.view">
        <field name="name">my.module.model.view.search</field>
        <field name="model">my.module.model</field>
        <field name="arch" type="xml">
            <search>
                <field name="name"/>
                <field name="partner_id"/>
                <field name="user_id"/>
                <separator/>
                <filter name="filter_draft" string="Draft" domain="[('state', '=', 'draft')]"/>
                <filter name="filter_confirmed" string="Confirmed" domain="[('state', '=', 'confirmed')]"/>
                <separator/>
                <filter name="filter_my_records" string="My Records" domain="[('user_id', '=', uid)]"/>
                <filter name="filter_archived" string="Archived" domain="[('active', '=', False)]"/>
                <separator/>
                <filter name="groupby_state" string="Status" context="{'group_by': 'state'}"/>
                <filter name="groupby_user" string="Responsible" context="{'group_by': 'user_id'}"/>
                <filter name="groupby_date" string="Date" context="{'group_by': 'date:month'}"/>
            </search>
        </field>
    </record>
</odoo>
```

`name=` on every `<page>` and `<filter>` so other modules can inherit them. Group-by filters
go directly under `<search>` — core no longer uses `<group expand="0" string="Group By">`.

---

## `views/my_model_menus.xml`

```xml
<odoo>
    <record id="my_model_action" model="ir.actions.act_window">
        <field name="name">My Models</field>
        <field name="res_model">my.module.model</field>
        <field name="view_mode">list,form</field>
        <field name="search_view_id" ref="my_model_view_search"/>
        <field name="context">{'search_default_filter_my_records': 1}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">Create your first record</p>
        </field>
    </record>

    <menuitem id="my_module_menu_root" name="My Module" sequence="100"
              groups="group_my_module_user"/>
    <menuitem id="my_module_menu_main" name="My Models" parent="my_module_menu_root"
              action="my_model_action" sequence="10"/>
</odoo>
```

`group_ids` (renamed from `groups_id` in 19.0) is the field name on `ir.actions.*` records; `groups=` on `<menuitem>` is still the shorthand attribute.

---

## `controllers/my_module.py` (only if there is an endpoint)

```python
from werkzeug.exceptions import BadRequest, NotFound

from odoo import http
from odoo.http import request


class MyModuleController(http.Controller):

    @http.route('/my_module/data', type='jsonrpc', auth='user', methods=['POST'])
    def get_data(self, record_id, **kwargs):
        """Return a summary after confirming the record exists and is readable."""
        if not isinstance(record_id, int) or isinstance(record_id, bool) or record_id <= 0:
            raise BadRequest("Invalid record id")
        record = request.env['my.module.model'].browse(record_id).exists()
        if not record:
            raise NotFound()
        record.check_access('read')
        return {'id': record.id, 'name': record.name, 'state': record.state}
```

Name controller files `<module_name>.py` or `<inherited_module>.py` (avoid legacy `main.py`).

---

## `tests/` — only when the user asked for tests

Do not add a `tests/` folder by default. When the user says yes, follow `testing.md` and start
from `BaseCommon` (available in Odoo 19 at `odoo/addons/base/tests/common.py`; never assume demo records exist):

```python
from odoo import fields
from odoo.addons.base.tests.common import BaseCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestMyModel(BaseCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.record = cls.env['my.module.model'].create({'date': fields.Date.context_today(cls.env['my.module.model'])})

    def test_confirm_from_draft(self):
        self.record.action_confirm()
        self.assertEqual(self.record.state, 'confirmed')

    def test_confirm_twice_raises(self):
        self.record.action_confirm()
        with self.assertRaises(UserError):
            self.record.action_confirm()
```

Note: In Odoo 19, `TransactionCase` / `BaseCommon` defaults to `at_install`; add `@tagged('post_install', '-at_install')` unless the test specifically must run at install time.

---

## `demo/demo_data.xml` (only if asked)

```xml
<odoo noupdate="1">
    <record id="demo_record_1" model="my.module.model">
        <field name="partner_id" ref="base.res_partner_2"/>
        <field name="user_id" ref="base.user_demo"/>
        <field name="date" eval="DateTime.today()"/>
    </record>
</odoo>
```
