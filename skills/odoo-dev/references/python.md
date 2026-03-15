# Python Best Practices — Odoo 19+ (Python 3.10+)

## Table of Contents

1. [Type Hints in Odoo](#1-type-hints-in-odoo)
2. [Generators and Lazy Evaluation](#2-generators-and-lazy-evaluation)
3. [Context Managers](#3-context-managers)
4. [Collections and Data Structures](#4-collections-and-data-structures)
5. [String Handling](#5-string-handling)
6. [Error Handling Patterns](#6-error-handling-patterns)
7. [Logging Standards](#7-logging-standards)
8. [Functional Patterns](#8-functional-patterns)
9. [Match Statements (3.10+)](#9-match-statements)
10. [Model Inheritance Patterns](#10-model-inheritance-patterns)
11. [ORM Method Overrides](#11-orm-method-overrides)
12. [Context Patterns](#12-context-patterns)
13. [Dangerous Antipatterns](#13-dangerous-antipatterns)

---

## 1. Type Hints in Odoo

Odoo core does NOT use type hints extensively, but for custom modules they
improve readability and IDE support. Use them on private/utility methods —
skip on ORM overrides (the framework types are complex).

```python
from collections.abc import Iterable

def _prepare_invoice_values(self) -> dict:
    """Prepare dictionary for account.move creation."""
    self.ensure_one()
    return {
        'partner_id': self.partner_id.id,
        'move_type': 'out_invoice',
    }

def _get_partner_ids_from_domain(self, domain: list) -> list[int]:
    """Extract partner IDs matching the given domain."""
    return self.env['res.partner'].search(domain).ids

def _split_into_batches(self, records, size: int = 200) -> Iterable:
    """Yield successive batches of the given size."""
    for i in range(0, len(records), size):
        yield records[i:i + size]
```

**Rules:**
- Use on private helpers and utility methods
- Skip on `create`, `write`, `unlink`, `search` overrides (signature is defined by ORM)
- Use `dict` not `Dict`, `list` not `List` (Python 3.10+)
- Use `X | None` not `Optional[X]` (Python 3.10+)

---

## 2. Generators and Lazy Evaluation

Use generators when processing large datasets to avoid loading everything into
memory at once. Critical for cron jobs and data migration.

```python
def _iter_pending_records(self, batch_size: int = 500):
    """Yield pending records in batches for memory-efficient processing.

    Yields:
        Recordset: A batch of records up to batch_size.
    """
    offset = 0
    while True:
        batch = self.search(
            [('state', '=', 'pending')],
            limit=batch_size,
            offset=offset,
            order='id',
        )
        if not batch:
            return
        yield batch
        offset += batch_size

def _cron_process_all(self):
    """Process all pending records in memory-safe batches."""
    for batch in self._iter_pending_records(batch_size=200):
        batch._process_batch()
        self.env.cr.commit()
        self.env.invalidate_all()
```

### Use `any()` / `all()` for short-circuit checks:
```python
# BAD — evaluates ALL records even if first one fails
has_draft = bool([r for r in self if r.state == 'draft'])

# GOOD — stops at first match
has_draft = any(r.state == 'draft' for r in self)

# GOOD — checks ALL pass
all_confirmed = all(r.state == 'confirmed' for r in self)
```

---

## 3. Context Managers

### Environment savepoints for atomic operations:
```python
def action_process_risky(self):
    """Process with rollback safety on partial failure."""
    for record in self:
        try:
            # Creates a SQL SAVEPOINT — rolls back on exception
            with self.env.cr.savepoint():
                record._do_risky_operation()
                record.write({'state': 'done'})
        except Exception:
            _logger.warning(
                "Failed to process record %s, skipping.", record.id,
                exc_info=True,
            )
            record.write({'state': 'error'})
```

### Temporary context change:
```python
# Use with_context for temporary env changes — don't mutate self.env.context
records_no_track = self.with_context(tracking_disable=True)
records_no_track.write({'state': 'done'})
# Original self still has normal context
```

### Suppress file operations:
```python
from contextlib import suppress

with suppress(FileNotFoundError):
    os.unlink(temp_file_path)
```

---

## 4. Collections and Data Structures

### defaultdict for grouping:
```python
from collections import defaultdict

def _group_lines_by_product(self):
    """Group order lines by product for consolidated processing.

    Returns:
        dict: Mapping of product_id to list of line recordsets.
    """
    grouped = defaultdict(lambda: self.env['sale.order.line'])
    for line in self.order_line:
        grouped[line.product_id] |= line  # recordset union
    return grouped
```

### Use `dict.setdefault` and `dict.get`:
```python
# BAD — verbose and error-prone
if key in my_dict:
    value = my_dict[key]
else:
    value = default_value

# GOOD
value = my_dict.get(key, default_value)

# Accumulating in a dict
vals = {}
vals.setdefault('invoice_line_ids', []).append((0, 0, line_vals))
```

### Tuple unpacking in loops:
```python
# BAD
for item in totals:
    order = item[0]
    total = item[1]

# GOOD — structured unpacking
for order, total in totals:
    order.amount_total = total

# With _read_group results:
totals = self.env['sale.order.line']._read_group(
    [('order_id', 'in', self.ids)],
    groupby=['order_id'],
    aggregates=['price_total:sum'],
)
totals_map = {order.id: total for order, total in totals}
```

---

## 5. String Handling

### Translation-safe string formatting:
```python
from odoo import _

# CORRECT — %s inside _() for translation extraction
msg = _("Order %s cannot be deleted (state: %s).", self.name, self.state)

# CORRECT — named placeholders for complex messages
msg = _("%(count)s orders for partner %(partner)s.", count=len(self), partner=self.partner_id.name)

# WRONG — f-string breaks translation tooling
msg = _(f"Order {self.name} cannot be deleted.")

# WRONG — .format() also breaks extraction
msg = _("Order {} cannot be deleted.".format(self.name))
```

### String building for large outputs:
```python
# BAD — O(n²) string concatenation
result = ""
for line in lines:
    result += line.name + "\n"

# GOOD — join a list
result = "\n".join(line.name for line in lines)
```

---

## 6. Error Handling Patterns

### Granular exception handling:
```python
# BAD — catches everything, hides bugs
try:
    record.action_confirm()
except Exception:
    pass

# GOOD — catch specific exceptions
from odoo.exceptions import UserError, ValidationError, AccessError

try:
    record.action_confirm()
except (UserError, ValidationError) as e:
    _logger.warning("Could not confirm %s: %s", record.name, e)
except AccessError:
    raise  # always re-raise access errors
```

### Use `ensure_one()` properly:
```python
# GOOD — at the start of single-record methods
def action_confirm(self):
    """Confirm this record."""
    self.ensure_one()  # raises ValueError if recordset is empty or multi
    ...

# GOOD — for optional single-record access
partner = self.env['res.partner'].search(domain, limit=1)
if partner:
    partner.do_something()  # safe, we know it's 0 or 1 records
```

### Never bare-except in production code:
```python
# FORBIDDEN in production
except:
    pass

# ACCEPTABLE only in truly defensive contexts (cron, mixin fallback)
# and always with logging:
except Exception:
    _logger.exception("Unexpected error processing %s", record)
```

---

## 7. Logging Standards

```python
import logging

_logger = logging.getLogger(__name__)

# Levels and when to use them:
_logger.debug("Query returned %d results", count)         # development only
_logger.info("Processing batch of %d records", len(self))  # normal operations
_logger.warning("Skipped record %s: missing partner", r.id)  # recoverable issues
_logger.error("Payment gateway returned error: %s", resp)    # non-fatal errors
_logger.exception("Unhandled error in cron job")              # with traceback

# RULES:
# 1. Always use lazy formatting (%, not f-strings)
_logger.info("Processing %s", record.name)      # GOOD — lazy
_logger.info(f"Processing {record.name}")        # BAD  — evaluated even if not logged

# 2. Use %r for untrusted values (shows repr with quotes)
_logger.warning("Invalid input: %r", user_input)

# 3. Never log sensitive data (passwords, tokens, PII)
_logger.info("Auth token: %s", token)  # FORBIDDEN

# 4. Use _logger.exception() inside except blocks (auto-includes traceback)
try:
    self._process()
except Exception:
    _logger.exception("Failed to process %s(%s)", self._name, self.id)
```

---

## 8. Functional Patterns

### Chained operations on recordsets:
```python
# Odoo recordsets support mapped/filtered/sorted natively
confirmed_partner_names = (
    self
    .filtered(lambda o: o.state == 'confirmed')
    .mapped('partner_id')
    .sorted('name')
    .mapped('name')
)
```

### Use `operator.itemgetter` for sorting dicts:
```python
from operator import itemgetter

# When sorting a list of dicts (common in report data)
data = [{'name': 'B', 'amount': 200}, {'name': 'A', 'amount': 100}]
sorted_data = sorted(data, key=itemgetter('amount'), reverse=True)
```

### Walrus operator (Python 3.8+, common in 3.10+):
```python
# Useful in Odoo for conditional processing
if partner := self.partner_id:
    partner.message_post(body=_("New order created."))

# In list comprehensions
valid = [
    inv
    for so in self
    if (inv := so.invoice_ids.filtered(lambda i: i.state == 'posted'))
]
```

---

## 9. Match Statements

Python 3.10+ structural pattern matching — useful for state machines and
dispatchers in Odoo.

```python
def _get_next_state(self) -> str:
    """Determine the next workflow state.

    Returns:
        str: The next state value.

    Raises:
        UserError: If current state has no valid transition.
    """
    match self.state:
        case 'draft':
            return 'confirmed'
        case 'confirmed':
            return 'in_progress'
        case 'in_progress':
            return 'done'
        case 'done' | 'cancelled':
            raise UserError(_("No transition from state '%s'.", self.state))
        case _:
            raise UserError(_("Unknown state: %s", self.state))

def _dispatch_action(self, action_type: str, **kwargs):
    """Dispatch to the correct handler based on action type."""
    match action_type:
        case 'email':
            return self._send_email(**kwargs)
        case 'sms':
            return self._send_sms(**kwargs)
        case 'webhook':
            return self._call_webhook(**kwargs)
        case _:
            _logger.warning("Unknown action type: %r", action_type)
```

---

## 10. Model Inheritance Patterns

Odoo has three distinct inheritance mechanisms. Confusing them is the #1
source of architectural mistakes.

### Classical Inheritance (`_inherit` without `_name`)
Extends an existing model in-place. No new DB table.

```python
class ResPartner(models.Model):
    """Add custom fields to the existing res.partner model."""

    _inherit = 'res.partner'

    loyalty_points = fields.Integer(string='Loyalty Points', default=0)

    def action_add_loyalty(self):
        """Add loyalty points to this partner."""
        self.loyalty_points += 10
```

**Use when:** Adding fields/methods/overrides to an existing model.
**DB effect:** Adds columns to the existing table.
**Key rule:** Do NOT set `_name` — that would create a new model.

### Prototype Inheritance (`_inherit` with new `_name`)
Copies the parent model into a new, independent model with its own table.

```python
class BookingOrder(models.Model):
    """New model based on sale.order structure."""

    _name = 'booking.order'
    _description = 'Booking Order'
    _inherit = 'sale.order'

    booking_date = fields.Datetime(string='Booking Date')
```

**Use when:** You want a new model that starts with the same schema as another.
**DB effect:** Creates a NEW table with all parent columns + your additions.
**Key rule:** Rarely used — most of the time you want classical or delegation.

### Delegation Inheritance (`_inherits`)
Composition pattern. The child model links to a parent record via a required
Many2one. Fields from the parent are accessible on the child transparently.

```python
class EventTicket(models.Model):
    """Event ticket that embeds a product.product record."""

    _name = 'event.ticket'
    _description = 'Event Ticket'
    _inherits = {'product.product': 'product_id'}

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='cascade',
    )
    event_id = fields.Many2one('event.event', string='Event', required=True)
```

**Use when:** Your model "is a" parent record (e.g., a ticket IS a product).
**DB effect:** New table with a FK to the parent. Parent record auto-created.
**Key rule:** Parent fields are read/write-through. `event_ticket.name` reads from `product_product.name`.

### Mixin Inheritance (`_inherit` with AbstractModel)
Reusable behavior that adds fields/methods without creating a table.

```python
class TrackingMixin(models.AbstractModel):
    """Mixin that adds GPS tracking fields."""

    _name = 'tracking.mixin'
    _description = 'GPS Tracking Mixin'

    latitude = fields.Float(string='Latitude', digits=(10, 7))
    longitude = fields.Float(string='Longitude', digits=(10, 7))
    last_tracked = fields.Datetime(string='Last Tracked')

    def action_update_location(self, lat, lng):
        """Update GPS coordinates."""
        self.write({
            'latitude': lat,
            'longitude': lng,
            'last_tracked': fields.Datetime.now(),
        })


class DeliveryOrder(models.Model):
    """Delivery order with GPS tracking."""

    _name = 'delivery.order'
    _description = 'Delivery Order'
    _inherit = ['mail.thread', 'tracking.mixin']  # multiple mixins

    name = fields.Char(string='Reference', required=True)
```

**Use when:** Sharing behavior across unrelated models (like `mail.thread`).
**DB effect:** Mixin columns are added to each model that inherits it.
**Key rule:** Use `AbstractModel` for the mixin — it has no table of its own.

### Quick Reference

| Pattern | `_name` | `_inherit` | New table? | Use case |
|---------|---------|------------|------------|----------|
| Classical | omit | `'existing.model'` | No | Add fields/override methods |
| Prototype | new name | `'existing.model'` | Yes | Clone schema into new model |
| Delegation | new name | omit | Yes (with FK) | "is-a" composition |
| Mixin | omit | `['mixin1', 'mixin2']` | No | Reusable behaviors |

---

## 11. ORM Method Overrides

### create() — always use `@api.model_create_multi`:
```python
@api.model_create_multi
def create(self, vals_list):
    """Create records with custom pre-processing.

    Always use @api.model_create_multi — the ORM calls create() with
    a list of dicts, and this decorator ensures batch creation works.
    """
    for vals in vals_list:
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('my.model') or _('New')
    return super().create(vals_list)
```

### write() — batch-aware override:
```python
def write(self, vals):
    """Override write to add side effects.

    Important: `self` is a multi-record recordset. Use `self.filtered()`
    if you need to act only on a subset.
    """
    if 'state' in vals and vals['state'] == 'done':
        # Pre-write validation on all records at once
        for record in self:
            if not record.line_ids:
                raise UserError(_("Cannot complete '%s': no lines.", record.name))
    result = super().write(vals)
    if 'state' in vals and vals['state'] == 'done':
        self._post_completion_actions()
    return result
```

### copy() — handle duplication:
```python
def copy(self, default=None):
    """Duplicate with modified name and reset state."""
    self.ensure_one()
    default = dict(default or {})
    default.setdefault('name', _("%s (copy)", self.name))
    return super().copy(default)
```

### _name_search — custom search-as-you-type:
```python
def _name_search(self, name='', domain=None, operator='ilike', limit=None, order=None):
    """Allow searching by reference code or name.

    This is called when typing in a Many2one field.
    """
    domain = domain or []
    if name:
        domain = ['|', ('name', operator, name), ('code', operator, name)] + domain
    return self._search(domain, limit=limit, order=order)
```

### _rec_name and _rec_names_search:
```python
class ProductVariant(models.Model):
    _name = 'product.variant'
    _description = 'Product Variant'
    _rec_name = 'display_name'  # field used for display_name
    _rec_names_search = ['name', 'default_code', 'barcode']  # fields searched in name_search
```

---

## 12. Context Patterns

### with_company() — switch company context:
```python
# When you need to read/write in another company's context
other_company = self.env['res.company'].browse(other_company_id)
record.with_company(other_company).write({'field': value})

# Common in multi-company logic
for company in self.env['res.company'].search([]):
    records = self.with_company(company).search([('company_id', '=', company.id)])
    records._process_for_company()
```

### with_context() — common patterns:
```python
# Skip mail tracking during bulk operations
self.with_context(tracking_disable=True).write(vals)

# Skip mail notifications during import
self.with_context(mail_create_nolog=True).create(vals_list)

# Force active_test=False to include archived records
all_records = self.with_context(active_test=False).search([])

# Pass default values to a sub-creation
self.with_context(default_partner_id=partner.id).action_open_wizard()

# Set allowed companies
self.with_context(allowed_company_ids=[company_1.id, company_2.id])
```

---

## 13. Dangerous Antipatterns

### Mutable default arguments:
```python
# BUG — the list is shared across all calls
def action_process(self, tags=[]):
    tags.append('processed')
    ...

# CORRECT
def action_process(self, tags=None):
    """Process with optional tags."""
    tags = tags or []
    tags.append('processed')
    ...
```

### Late binding in closures (lambdas in loops):
```python
# BUG — all lambdas capture the LAST value of `rec`
handlers = []
for rec in self:
    handlers.append(lambda: rec.action_confirm())
# All handlers will confirm the LAST record!

# CORRECT — bind with default argument
handlers = []
for rec in self:
    handlers.append(lambda r=rec: r.action_confirm())
```

### Comparing with `is` vs `==`:
```python
# Use `is` ONLY for singletons (None, True, False)
if value is None:      # CORRECT
if value is False:     # CORRECT
if value == 0:         # CORRECT (0 is not False in Odoo context)
if record is True:     # WRONG for Odoo — recordsets are truthy/falsy

# For recordsets, use truthiness:
if record:             # CORRECT — non-empty recordset
if not record:         # CORRECT — empty recordset
```

### Never modify `self` during iteration:
```python
# BUG — modifying the recordset you're iterating
for record in self:
    if record.state == 'cancelled':
        self -= record  # UNDEFINED BEHAVIOR

# CORRECT — filter first, then act
to_process = self.filtered(lambda r: r.state != 'cancelled')
for record in to_process:
    record._process()
```

### Avoid `eval()` / `exec()`:
```python
# FORBIDDEN — arbitrary code execution
domain = eval(user_provided_string)

# CORRECT — use ast.literal_eval for safe literals
import ast
domain = ast.literal_eval(user_provided_string)

# BEST — use json.loads if the format permits
import json
domain = json.loads(user_provided_string)
```
