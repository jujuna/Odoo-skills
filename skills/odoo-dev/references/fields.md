# Fields — Odoo 19+

## 1. Field Types Overview

| Type | Python class | DB column | Key kwargs |
|---|---|---|---|
| `Char` | `fields.Char` | `varchar` | `size`, `trim`, `translate` |
| `Text` | `fields.Text` | `text` | `translate` |
| `Html` | `fields.Html` | `text` | `translate`, `sanitize` |
| `Integer` | `fields.Integer` | `int4` | |
| `Float` | `fields.Float` | `float8` | `digits=(precision, scale)` |
| `Monetary` | `fields.Monetary` | `numeric` | `currency_field` |
| `Boolean` | `fields.Boolean` | `bool` | |
| `Date` | `fields.Date` | `date` | |
| `Datetime` | `fields.Datetime` | `timestamp` | UTC in DB |
| `Binary` | `fields.Binary` | `bytea` | `attachment` |
| `Image` | `fields.Image` | `bytea` | `max_width`, `max_height` |
| `Selection` | `fields.Selection` | `varchar` | `selection`, `group_expand` |
| `Reference` | `fields.Reference` | `varchar` | `selection` |
| `Many2one` | `fields.Many2one` | `int4` (FK) | `ondelete`, `check_company`, `domain` |
| `One2many` | `fields.One2many` | _(virtual)_ | `comodel_name`, `inverse_name` |
| `Many2many` | `fields.Many2many` | _(junction)_ | `relation`, `column1`, `column2` |
| `Properties` | `fields.Properties` | `jsonb` | `definition_record` |
| `Json` | `fields.Json` | `jsonb` | |
