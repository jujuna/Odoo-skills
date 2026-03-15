# Performance Patterns — Odoo 19+

## Table of Contents

1. [The N+1 Problem](#1-the-n1-problem)
2. [Batch Operations](#2-batch-operations)
3. [Prefetching and Caching](#3-prefetching-and-caching)
4. [Search Optimization](#4-search-optimization)
5. [Computed Fields Strategy](#5-computed-fields-strategy)
6. [Write Optimization](#6-write-optimization)
7. [Database Indexes](#7-database-indexes)
8. [Recordset Operations](#8-recordset-operations)
9. [Memory Management](#9-memory-management)
10. [Profiling](#10-profiling)
11. [Relational Search Access](#11-relational-search-access)
12. [with_prefetch() Control](#12-with_prefetch-control)
13. [_order Performance](#13-_order-performance)
14. [Flush and Invalidate](#14-flush-and-invalidate)
15. [ORM vs Raw SQL Decision Matrix](#15-orm-vs-raw-sql-decision-matrix)

---

## 1. The N+1 Problem

The most common Odoo performance issue. Happens when you query inside a loop.

### BAD — N+1 queries:
```python
def _compute_partner_email(self):
    for record in self:
        # This triggers a separate query for EACH record
        partner = self.env['res.partner'].search([('id', '=', record.partner_id.id)])
        record.partner_email = partner.email
```

### GOOD — Single query via prefetch:
```python
def _compute_partner_email(self):
    # Odoo auto-prefetches related fields on the same recordset
    for record in self:
        record.partner_email = record.partner_id.email
```

### GOOD — Explicit batch when needed:
```python
def action_send_emails(self):
    """Send emails to all selected partners."""
    # Pre-load all partners in one query
    partners = self.mapped('partner_id')
    # Now iterate — no additional queries
    for partner in partners:
        partner._send_notification_email()
```

---

## 2. Batch Operations

### create() — Always use multi-create:
```python
# BAD — N create calls
for vals in vals_list:
    self.env['my.model'].create(vals)

# GOOD — Single multi-create
self.env['my.model'].create(vals_list)
```

### write() — Batch when possible:
```python
# BAD — N write calls
for record in records:
    record.write({'state': 'done'})

# GOOD — Single write call
records.write({'state': 'done'})

# GOOD — When values differ, group by value
from itertools import groupby
for state, group_records in groupby(records, key=lambda r: r.computed_state):
    self.env['my.model'].browse([r.id for r in group_records]).write({'state': state})
```

### unlink() — Batch:
```python
# BAD
for record in records:
    record.unlink()

# GOOD
records.unlink()
```

---

## 3. Prefetching and Caching

### How Odoo prefetching works:
When you access a field on one record, Odoo loads that field for ALL records
in the same recordset (same prefetch group). Use this to your advantage.

```python
# The first access to record.name loads 'name' for ALL records in self
for record in self:
    print(record.name)  # Only 1 SQL query total, not N
```

### When prefetching breaks:
```python
# BAD — breaks prefetching by creating single-record recordsets
for record_id in self.ids:
    record = self.env['my.model'].browse(record_id)
    print(record.name)  # N queries!

# GOOD — iterate the recordset directly
for record in self:
    print(record.name)  # 1 query total
```

### Explicit prefetch for cross-model reads:
```python
def _process_orders(self):
    """Process orders with optimized field loading."""
    orders = self.search([('state', '=', 'pending')])
    # Force-read fields we'll need, in one batch
    orders.mapped('partner_id.name')
    orders.mapped('order_line_ids.product_id.name')
    # Now iterate — all data is cached
    for order in orders:
        self._process_single_order(order)
```

---

## 4. Search Optimization

### Use search_fetch() (v18+):
```python
# OLD — Two separate queries
records = self.search(domain)
data = records.read(['name', 'state', 'amount'])

# NEW — Combined search + fetch in one query
records = self.search_fetch(domain, ['name', 'state', 'amount'], limit=100)
```

### search_count with limit:
```python
# When you only need to know "are there more than X?"
has_many = self.search_count(domain, limit=100) >= 100
```

### Efficient existence check:
```python
# BAD — loads all matching records
if self.search([('partner_id', '=', partner.id)]):
    ...

# GOOD — stops at first match
if self.search([('partner_id', '=', partner.id)], limit=1):
    ...

# ALSO GOOD — count with limit
if self.search_count([('partner_id', '=', partner.id)], limit=1):
    ...
```

### Use domain optimization:
```python
# Put indexed / most-selective fields first in domains
domain = [
    ('company_id', '=', self.env.company.id),  # indexed, very selective
    ('state', '=', 'confirmed'),                # indexed selection
    ('date', '>=', start_date),                 # indexed date range
    ('name', 'ilike', search_term),             # unindexed text search — last
]
```

---

## 5. Computed Fields Strategy

### When to store:
```python
# STORE when:
# - Field is used in search/filter/group_by
# - Field is displayed in list views (computed per page load)
# - Computation is expensive
# - Dependencies change infrequently
total = fields.Float(compute='_compute_total', store=True)
```

### When NOT to store:
```python
# DON'T STORE when:
# - Dependencies change on almost every write
# - Field is only on form view (single record)
# - Storage cost outweighs computation cost
current_age = fields.Integer(compute='_compute_current_age')  # changes daily
```

### Optimize compute methods:
```python
@api.depends('line_ids.price_total')
def _compute_amount_total(self):
    """Compute total amount from order lines.

    Optimized: uses read_group for batch aggregation instead of
    iterating lines per record.
    """
    if not self.ids:
        for record in self:
            record.amount_total = 0.0
        return
    # Batch aggregation — one SQL query for all records
    totals = self.env['my.model.line']._read_group(
        [('order_id', 'in', self.ids)],
        groupby=['order_id'],
        aggregates=['price_total:sum'],
    )
    totals_map = {order.id: total for order, total in totals}
    for record in self:
        record.amount_total = totals_map.get(record.id, 0.0)
```

---

## 6. Write Optimization

### Avoid triggering unnecessary recomputation:
```python
# BAD — each write triggers recomputation of dependents
for record in self:
    record.field_a = value_a
    record.field_b = value_b  # triggers recompute AGAIN

# GOOD — single write, one recomputation pass
for record in self:
    record.write({'field_a': value_a, 'field_b': value_b})

# BEST — batch write when values are the same
self.write({'field_a': value_a, 'field_b': value_b})
```

### Use with_context to skip unnecessary operations:
```python
# Skip mail notifications during bulk import
records.with_context(mail_create_nolog=True, tracking_disable=True).create(vals_list)
```

---

## 7. Database Indexes

### v19 syntax for indexes:
```python
class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'

    # Field-level index
    partner_id = fields.Many2one('res.partner', index=True)
    state = fields.Selection([...], index=True)
    date = fields.Date(index=True)

    # Composite indexes (v19): declare named class attributes
    _partner_state_idx = models.Index("(partner_id, state)")
    _company_date_idx = models.Index("(company_id, date)")
```

### Index guidelines:
- Always index: `Many2one` fields, `state`/`status` fields, date fields used in search
- Index `company_id` — always used in record rules
- Add composite indexes for common search combinations
- Don't over-index: each index slows down writes

---

## 8. Recordset Operations

### Efficient recordset manipulation:
```python
# Filtering — use filtered_domain for SQL-backed filtering
confirmed = self.filtered_domain([('state', '=', 'confirmed')])

# Mapping — collect related field values
partner_names = self.mapped('partner_id.name')  # returns list
partner_ids = self.mapped('partner_id')  # returns recordset

# Sorting
sorted_records = self.sorted(key=lambda r: r.date, reverse=True)

# Deduplication
unique_partners = self.mapped('partner_id')  # already deduplicated for recordsets
```

### Avoid Python-side filtering when DB can do it:
```python
# BAD — loads ALL records then filters in Python
all_records = self.search([])
filtered = all_records.filtered(lambda r: r.amount > 1000 and r.state == 'confirmed')

# GOOD — let the database do the filtering
filtered = self.search([('amount', '>', 1000), ('state', '=', 'confirmed')])
```

---

## 9. Memory Management

### Large recordset processing:
```python
def _cron_process_large_batch(self):
    """Process records in chunks to control memory usage."""
    batch_size = 200
    offset = 0
    while True:
        records = self.search(
            [('state', '=', 'pending')],
            limit=batch_size,
            offset=offset,
            order='id',
        )
        if not records:
            break
        records._process_batch()
        # Commit and clear cache after each batch
        self.env.cr.commit()
        self.env.invalidate_all()
        offset += batch_size
```

### Avoid loading large binary fields:
```python
# BAD — loads binary data for all records
records = self.search([])
for r in records:
    if r.attachment_data:  # loads potentially huge binary
        ...

# GOOD — only load binary when needed
records = self.search_fetch(domain, ['name', 'state'])  # no binary
for r in records:
    if r.has_attachment:  # boolean check first
        data = r.attachment_data  # load binary only when needed
```

---

## 10. Profiling

### Enable Odoo profiling:
```python
# In your method, for debugging:
from odoo.tools.profiler import profile

@profile('/tmp/my_profile.log')
def action_heavy_computation(self):
    """Profile this method to find bottlenecks."""
    ...
```

### Quick query counting:
```python
import logging
_logger = logging.getLogger(__name__)

def action_debug_performance(self):
    """Count SQL queries for debugging."""
    cr = self.env.cr
    query_count_before = cr.sql_log_count
    # ... your code ...
    query_count_after = cr.sql_log_count
    _logger.info("Queries executed: %d", query_count_after - query_count_before)
```

### Key metrics to watch:
- **Query count**: Should be O(1) or O(models), never O(records)
- **Query time**: Use `--log-sql` flag to see slow queries
- **Memory**: Watch for large recordsets held in memory
- **Recomputation chains**: Long `@api.depends` chains can cascade

---

## 11. Relational Search Access

In Odoo 19, use `bypass_search_access` intentionally on relational fields when you
need to bypass comodel search access checks. This is primarily a security behavior,
not a generic performance switch.

```python
class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'

    # Default and safest: respects comodel access checks
    partner_id = fields.Many2one('res.partner')

    # Use only when there is an explicit security reason and documented scope
    # (for example, controlled technical lookups where record exposure is filtered separately)
    technical_partner_id = fields.Many2one('res.partner', bypass_search_access=True)
```

**Rules:**
- Prefer normal relational fields (default access checks) in business code
- Treat `bypass_search_access=True` as security-sensitive and justify it with a comment
- Optimize search performance with proper domains and indexes, not access-bypass flags

---

## 12. with_prefetch() Control

Control the prefetch group to optimize memory usage when processing
subsets of a large recordset.

```python
def _process_in_chunks(self, records):
    """Process records with controlled prefetch groups.

    By default, accessing ANY field on one record prefetches that field
    for ALL records in the same recordset. For 100k records, this loads
    100k values into memory even if you process 100 at a time.
    """
    chunk_size = 200
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        # with_prefetch() creates a new prefetch group limited to this chunk
        # so only 200 records are loaded into memory at a time
        for record in chunk.with_prefetch():
            record._do_expensive_work()
```

**When to use:**
- Processing very large recordsets (10k+) where you don't need all data in memory
- When combined with `cr.commit()` in batch processing

---

## 13. _order Performance

The `_order` attribute generates an ORDER BY clause on EVERY `search()`.
A bad `_order` can destroy performance.

```python
# BAD — sorts by a computed non-stored field (Python sort, not SQL)
_order = 'display_name'

# BAD — sorts by a non-indexed field on a large table
_order = 'description desc'

# GOOD — sorts by indexed fields
_order = 'create_date desc, id desc'

# GOOD — if you need to sort by date, make sure it's indexed
_order = 'date_order desc, id desc'
date_order = fields.Datetime(index=True)

# BEST — for large tables, always include `id` as tiebreaker for deterministic results
_order = 'sequence, id'
```

**Rules:**
- Always include `id` in `_order` as a tiebreaker (prevents non-deterministic pagination)
- Every field in `_order` should be indexed
- Never use non-stored computed fields in `_order` (triggers Python-side sort)
- For inherited models, check the parent's `_order` — you inherit it

---

## 14. Flush and Invalidate

Understanding when to flush/invalidate is critical for correct behavior
when mixing ORM and raw SQL.

```python
# After ORM operations, before raw SQL reads:
self.env.flush_all()  # writes all pending ORM changes to database
self.env.cr.execute("SELECT ...")  # now sees the latest data

# After raw SQL writes, before ORM reads:
self.env.cr.execute("UPDATE my_model SET state = 'done' WHERE ...")
self.env.invalidate_all()  # clears ORM cache so it re-reads from DB

# Per-recordset variants (more targeted, less overhead):
records.flush_recordset(['field_a', 'field_b'])  # flush specific fields
records.invalidate_recordset(['field_a'])  # invalidate specific fields
```

**Rules:**
- `flush_all()` before any raw SQL SELECT that reads data you changed via ORM
- `invalidate_all()` after any raw SQL UPDATE/DELETE that changes data ORM might have cached
- After `cr.commit()` always call `invalidate_all()` — the cache may reference rolled-back data
- Prefer `flush_recordset`/`invalidate_recordset` over `_all` variants for better performance

---

## 15. ORM vs Raw SQL Decision Matrix

| Scenario | Use ORM | Use Raw SQL |
|----------|---------|-------------|
| Simple CRUD (create/read/update/delete) | Yes | No |
| Search with domain filters | Yes (`search()`) | No |
| Grouped aggregation (SUM, COUNT, AVG) | Yes (`_read_group()`) | Only if ORM too slow |
| Window functions (RANK, ROW_NUMBER, running totals) | No | Yes |
| Bulk update 10k+ rows without triggers | No | Yes |
| Complex JOINs across 4+ tables | Maybe | Usually yes |
| LATERAL JOIN, CTE, recursive queries | No | Yes |
| EXISTS subquery for performance | No | Yes |
| INSERT ... ON CONFLICT (upsert) | No | Yes |
| SELECT FOR UPDATE (row locking) | No | Yes |
| Dashboard KPI (single fast query) | Depends | Often yes |
| COPY command for bulk data import | No | Yes |

**Always remember:** Raw SQL bypasses security (ACLs, record rules), tracking,
computed fields, and constraints. Every raw SQL usage needs explicit justification.
