# Module Scaffold — Odoo 19+

Complete copy-paste-ready templates for a new Odoo 19 module.

---

## Full Module Layout

```
my_module/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py
├── data/
│   └── sequence_data.xml
├── demo/
│   └── demo_data.xml
├── models/
│   ├── __init__.py
│   └── my_model.py
├── report/
│   ├── __init__.py
│   ├── my_model_report.py        (optional: custom report parser)
│   └── my_model_report_templates.xml
├── security/
│   ├── groups.xml
│   ├── ir.model.access.csv
│   └── rules.xml
├── static/
│   ├── description/
│   │   └── icon.png              (module icon, 128x128 or 256x256)
│   └── src/
│       ├── components/
│       │   └── my_component/
│       │       ├── my_component.js
│       │       ├── my_component.xml
│       │       └── my_component.scss
│       └── scss/
│           └── my_module.scss
├── tests/
│   ├── __init__.py
│   └── test_my_model.py
├── views/
│   ├── menu.xml
│   └── my_model_views.xml
└── wizards/
    ├── __init__.py
    ├── my_wizard.py
    └── my_wizard_views.xml
```

**Note:** `static/description/icon.png` is the module icon shown in the Apps screen. Use 128x128 or 256x256 PNG.

---

## File: `__manifest__.py`

```python
{
    'name': 'MODULE_TITLE',
    'version': '19.0.1.0.0',
    'category': 'CATEGORY',
    'summary': 'SHORT_SUMMARY',
    'description': """
        LONG_DESCRIPTION
    """,
    'author': 'AUTHOR',
    'website': 'WEBSITE',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        # Security first
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        # Data
        'data/sequence_data.xml',
        # Views
        'views/my_model_views.xml',
        'views/menu.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
}
```

---

## File: `__init__.py`

```python
from . import controllers
from . import models
from . import wizards
```

---

## File: `models/__init__.py`

```python
from . import my_model
```

---

## File: `models/my_model.py`

```python
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

_logger = logging.getLogger(__name__)


class MyModel(models.Model):
    """Main model for MODULE_TITLE.

    Manages the lifecycle of [DESCRIPTION] from draft to completion.
    Supports mail thread for communication tracking.
    """

    _name = 'my.module.model'
    _description = 'My Model'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, name'

    # --- Default methods ---
    @api.model
    def _default_company_id(self):
        """Return the current user's company as default."""
        return self.env.company

    # --- Fields ---
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        copy=False,
        default='draft',
        tracking=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=_default_company_id,
        index=True,
    )
    line_ids = fields.One2many(
        'my.module.model.line',
        'order_id',
        string='Lines',
    )
    notes = fields.Html(string='Notes')

    # Computed
    line_count = fields.Integer(
        string='Line Count',
        compute='_compute_line_count',
        store=True,
    )

    # --- Compute methods ---
    @api.depends('line_ids')
    def _compute_line_count(self):
        """Compute the number of lines per record."""
        for record in self:
            record.line_count = len(record.line_ids)

    # --- Constraints ---
    @api.constrains('date')
    def _check_date_not_past(self):
        """Ensure the date is not in the past for new records."""
        for record in self:
            if record.date and record.date < fields.Date.today() and record.state == 'draft':
                raise ValidationError(
                    _("Date cannot be in the past for draft records.")
                )

    # --- CRUD overrides ---
    @api.model_create_multi
    def create(self, vals_list):
        """Create records with auto-generated sequence reference.

        Args:
            vals_list: List of dictionaries with field values.

        Returns:
            Recordset of newly created records.
        """
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'my.module.model'
                ) or _('New')
        return super().create(vals_list)

    def copy(self, default=None):
        """Duplicate record with modified name.

        Args:
            default: Dictionary of field values to override.

        Returns:
            New duplicated record.
        """
        self.ensure_one()
        default = dict(default or {})
        default.setdefault('name', _("%s (copy)", self.name))
        return super().copy(default)

    # --- Action methods ---
    def action_confirm(self):
        """Confirm the record and transition to 'confirmed' state.

        Returns:
            bool: True on success.

        Raises:
            UserError: If the record is not in draft state.
        """
        for record in self:
            if record.state != 'draft':
                raise UserError(
                    _("Only draft records can be confirmed. '%s' is in state '%s'.",
                      record.name, record.state)
                )
            record.write({'state': 'confirmed'})
        return True

    def action_done(self):
        """Mark the record as done.

        Returns:
            bool: True on success.

        Raises:
            UserError: If the record is not in confirmed state.
        """
        for record in self:
            if record.state != 'confirmed':
                raise UserError(_("Only confirmed records can be marked as done."))
            record.write({'state': 'done'})
        return True

    def action_cancel(self):
        """Cancel the record.

        Returns:
            bool: True on success.
        """
        self.write({'state': 'cancelled'})
        return True

    def action_draft(self):
        """Reset the record to draft state.

        Returns:
            bool: True on success.
        """
        self.write({'state': 'draft'})
        return True


class MyModelLine(models.Model):
    """Line items for MyModel."""

    _name = 'my.module.model.line'
    _description = 'My Model Line'
    _order = 'sequence, id'

    order_id = fields.Many2one(
        'my.module.model',
        string='Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Description', required=True)
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    price_unit = fields.Float(string='Unit Price')
    price_total = fields.Float(
        string='Total',
        compute='_compute_price_total',
        store=True,
    )
    company_id = fields.Many2one(
        related='order_id.company_id',
        store=True,
    )

    @api.depends('quantity', 'price_unit')
    def _compute_price_total(self):
        """Compute total price as quantity * unit price."""
        for line in self:
            line.price_total = line.quantity * line.price_unit
```

---

## File: `security/groups.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="module_category_my_module" model="ir.module.category">
        <field name="name">My Module</field>
        <field name="sequence">20</field>
    </record>

    <record id="group_my_module_user" model="res.groups">
        <field name="name">User</field>
        <field name="category_id" ref="module_category_my_module"/>
        <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
    </record>

    <record id="group_my_module_manager" model="res.groups">
        <field name="name">Manager</field>
        <field name="category_id" ref="module_category_my_module"/>
        <field name="implied_ids" eval="[(4, ref('group_my_module_user'))]"/>
        <field name="users" eval="[(4, ref('base.user_root')), (4, ref('base.user_admin'))]"/>
    </record>
</odoo>
```

---

## File: `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_my_module_model_user,my.module.model.user,model_my_module_model,group_my_module_user,1,1,1,0
access_my_module_model_manager,my.module.model.manager,model_my_module_model,group_my_module_manager,1,1,1,1
access_my_module_model_line_user,my.module.model.line.user,model_my_module_model_line,group_my_module_user,1,1,1,1
access_my_module_model_line_manager,my.module.model.line.manager,model_my_module_model_line,group_my_module_manager,1,1,1,1
```

---

## File: `security/rules.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Multi-company rule (global) -->
    <record id="rule_my_module_model_company" model="ir.rule">
        <field name="name">My Model: Multi-Company</field>
        <field name="model_id" ref="model_my_module_model"/>
        <field name="domain_force">
            ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
        </field>
    </record>

    <!-- User: own records or unassigned -->
    <record id="rule_my_module_model_user" model="ir.rule">
        <field name="name">My Model: User Own Records</field>
        <field name="model_id" ref="model_my_module_model"/>
        <field name="domain_force">
            ['|', ('user_id', '=', user.id), ('user_id', '=', False)]
        </field>
        <field name="groups" eval="[(4, ref('group_my_module_user'))]"/>
    </record>

    <!-- Manager: all records -->
    <record id="rule_my_module_model_manager" model="ir.rule">
        <field name="name">My Model: Manager All Records</field>
        <field name="model_id" ref="model_my_module_model"/>
        <field name="domain_force">[(1, '=', 1)]</field>
        <field name="groups" eval="[(4, ref('group_my_module_manager'))]"/>
    </record>
</odoo>
```

---

## File: `data/sequence_data.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="seq_my_module_model" model="ir.sequence">
        <field name="name">My Model Sequence</field>
        <field name="code">my.module.model</field>
        <field name="prefix">MM/%(year)s/</field>
        <field name="padding">5</field>
        <field name="company_id" eval="False"/>
    </record>
</odoo>
```

---

## File: `views/my_model_views.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Form View -->
    <record id="my_module_model_view_form" model="ir.ui.view">
        <field name="name">my.module.model.view.form</field>
        <field name="model">my.module.model</field>
        <field name="arch" type="xml">
            <form string="My Model">
                <header>
                    <button name="action_confirm" type="object"
                            string="Confirm" class="oe_highlight"
                            invisible="state != 'draft'"/>
                    <button name="action_done" type="object"
                            string="Done" class="oe_highlight"
                            invisible="state != 'confirmed'"/>
                    <button name="action_cancel" type="object"
                            string="Cancel"
                            invisible="state in ('done', 'cancelled')"/>
                    <button name="action_draft" type="object"
                            string="Reset to Draft"
                            invisible="state not in ('cancelled',)"/>
                    <field name="state" widget="statusbar"
                           statusbar_visible="draft,confirmed,done"/>
                </header>
                <sheet>
                    <div class="oe_button_box" name="button_box">
                    </div>
                    <div class="oe_title">
                        <h1>
                            <field name="name" readonly="1"/>
                        </h1>
                    </div>
                    <group>
                        <group>
                            <field name="partner_id"/>
                            <field name="user_id"/>
                            <field name="date"/>
                        </group>
                        <group>
                            <field name="company_id" groups="base.group_multi_company"/>
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
                                </list>
                            </field>
                        </page>
                        <page string="Notes" name="notes">
                            <field name="notes" placeholder="Add internal notes here..."/>
                        </page>
                    </notebook>
                </sheet>
                <chatter/>
            </form>
        </field>
    </record>

    <!-- List View -->
    <record id="my_module_model_view_list" model="ir.ui.view">
        <field name="name">my.module.model.view.list</field>
        <field name="model">my.module.model</field>
        <field name="arch" type="xml">
            <list string="My Models" multi_edit="1" default_order="date desc">
                <field name="name" decoration-bf="1"/>
                <field name="partner_id"/>
                <field name="user_id"/>
                <field name="date"/>
                <field name="line_count"/>
                <field name="state"
                       decoration-success="state == 'done'"
                       decoration-info="state == 'confirmed'"
                       decoration-muted="state == 'cancelled'"
                       widget="badge"/>
            </list>
        </field>
    </record>

    <!-- Search View -->
    <record id="my_module_model_view_search" model="ir.ui.view">
        <field name="name">my.module.model.view.search</field>
        <field name="model">my.module.model</field>
        <field name="arch" type="xml">
            <search string="Search">
                <field name="name"/>
                <field name="partner_id"/>
                <field name="user_id"/>
                <separator/>
                <filter name="filter_draft" string="Draft"
                        domain="[('state', '=', 'draft')]"/>
                <filter name="filter_confirmed" string="Confirmed"
                        domain="[('state', '=', 'confirmed')]"/>
                <filter name="filter_done" string="Done"
                        domain="[('state', '=', 'done')]"/>
                <separator/>
                <filter name="filter_my_records" string="My Records"
                        domain="[('user_id', '=', uid)]"/>
                <separator/>
                <filter name="filter_archived" string="Archived"
                        domain="[('active', '=', False)]"/>
                <group expand="0" string="Group By">
                    <filter name="groupby_state" string="Status"
                            context="{'group_by': 'state'}"/>
                    <filter name="groupby_user" string="Responsible"
                            context="{'group_by': 'user_id'}"/>
                    <filter name="groupby_partner" string="Partner"
                            context="{'group_by': 'partner_id'}"/>
                    <filter name="groupby_date" string="Date"
                            context="{'group_by': 'date:month'}"/>
                </group>
            </search>
        </field>
    </record>
</odoo>
```

---

## File: `views/menu.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- Action -->
    <record id="my_module_model_action" model="ir.actions.act_window">
        <field name="name">My Models</field>
        <field name="res_model">my.module.model</field>
        <field name="view_mode">list,form</field>
        <field name="search_view_id" ref="my_module_model_view_search"/>
        <field name="context">{'search_default_filter_my_records': 1}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                Create your first record
            </p>
            <p>
                Click the "New" button to get started.
            </p>
        </field>
    </record>

    <!-- Root Menu -->
    <menuitem id="my_module_menu_root"
              name="My Module"
              sequence="100"
              groups="group_my_module_user"/>

    <!-- Sub Menus -->
    <menuitem id="my_module_menu_main"
              name="My Models"
              parent="my_module_menu_root"
              action="my_module_model_action"
              sequence="10"/>
</odoo>
```

---

## File: `tests/__init__.py`

```python
from . import test_my_model
```

---

## File: `tests/test_my_model.py`

```python
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestMyModel(TransactionCase):
    """Test cases for my.module.model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
        })
        cls.record = cls.env['my.module.model'].create({
            'partner_id': cls.partner.id,
            'date': fields.Date.today(),
        })

    def test_create_generates_sequence(self):
        """Test that create assigns a sequence reference."""
        self.assertNotEqual(self.record.name, 'New')
        self.assertTrue(self.record.name.startswith('MM/'))

    def test_action_confirm_from_draft(self):
        """Test confirming a draft record transitions to confirmed."""
        self.assertEqual(self.record.state, 'draft')
        self.record.action_confirm()
        self.assertEqual(self.record.state, 'confirmed')

    def test_action_confirm_not_draft_raises(self):
        """Test confirming a non-draft record raises UserError."""
        self.record.action_confirm()
        with self.assertRaises(UserError):
            self.record.action_confirm()

    def test_line_count_computed(self):
        """Test that line count is correctly computed."""
        self.assertEqual(self.record.line_count, 0)
        self.env['my.module.model.line'].create({
            'order_id': self.record.id,
            'name': 'Test Line',
            'quantity': 5,
            'price_unit': 10.0,
        })
        self.assertEqual(self.record.line_count, 1)
```

---

## File: `controllers/__init__.py`

```python
from . import main
```

---

## File: `controllers/main.py`

```python
from odoo import http
from odoo.http import request


class MyModuleController(http.Controller):
    """HTTP controllers for my module."""

    @http.route('/my_module/data', type='jsonrpc', auth='user', methods=['POST'])
    def get_data(self, record_id, **kwargs):
        """Fetch record data for authenticated users.

        Args:
            record_id (int): ID of the record to fetch.

        Returns:
            dict: Record data.
        """
        if not isinstance(record_id, int) or record_id <= 0:
            raise ValueError("Invalid record ID")

        record = request.env['my.module.model'].browse(record_id)
        record.check_access('read')
        return {
            'id': record.id,
            'name': record.name,
            'state': record.state,
        }
```

---

## File: `wizards/__init__.py`

```python
from . import my_wizard
```

---

## File: `demo/demo_data.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <record id="demo_record_1" model="my.module.model">
            <field name="partner_id" ref="base.res_partner_2"/>
            <field name="user_id" ref="base.user_demo"/>
            <field name="date" eval="DateTime.today()"/>
        </record>
    </data>
</odoo>
```
