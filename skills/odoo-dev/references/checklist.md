# Quality Checklist — Odoo 19+

Run through this checklist before returning any code. Every item is a potential bug or review blocker.

---

## Python / ORM

- [ ] New model has `_description`
- [ ] New or modified methods have a meaningful docstring
- [ ] Public ORM methods are batch-safe; no accidental singleton assumptions
- [ ] `ensure_one()` appears only where one record is truly required
- [ ] `create()` overrides use `@api.model_create_multi` and call `super()` once
- [ ] `write()`/`unlink()` overrides validate in batch and avoid per-record `super()` calls
- [ ] No deprecated APIs: `read_group()`, `name_get()`, `type='json'`
- [ ] No N+1 queries in compute/business methods
- [ ] Batch operations used for create/write/unlink where possible
- [ ] Compute methods assign every record and avoid side-effect writes
- [ ] Dynamic domains use `odoo.fields.Domain` instead of brittle prefix-list assembly
- [ ] Relational updates use `odoo.Command` helpers, not raw magic tuples
- [ ] `sudo()` is justified with inline comment + pre-validation
- [ ] User-facing text uses `_()` with `%s`; no f-strings inside `_()`
- [ ] `_logger` uses lazy formatting (`%s`)
- [ ] Raw SQL is parameterized; cache invalidated after SQL writes
- [ ] Float comparisons use `float_compare` / `float_is_zero`
- [ ] Delete restrictions use `@api.ondelete`
- [ ] No mutable default arguments
- [ ] Indexes use `models.Index("(col1, col2)")` named class attributes
- [ ] Domain API uses `from odoo.fields import Domain`
- [ ] Manual `cr.commit()` appears only in resumable cron/import/migration code
- [ ] Manual commit paths guard tests (`_can_commit`) and invalidate env after commit
- [ ] Raw SQL writes call targeted invalidate and `modified()` when recompute dependencies changed

## Fields

- [ ] Monetary fields have `currency_id` M2O + `currency_field='currency_id'`
- [ ] `Date.today` / `Datetime.now` defaults are callable (no parentheses)
- [ ] Many2one has explicit `ondelete` on business-critical relations
- [ ] Multi-company: `company_id` has `index=True`; related M2O has `check_company=True`
- [ ] Cross-company logic groups by company and uses `with_company(company)`
- [ ] Related fields used in search/groupby have `store=True`
- [ ] `@api.onchange` is UX-only; real logic is in `@api.depends`
- [ ] `copy=False` on sequences, states, unique refs

## Security

- [ ] Security files exist and are FIRST in manifest `data`
- [ ] Every new model has ACL entries in `ir.model.access.csv`
- [ ] Sensitive fields have `groups=` restriction
- [ ] Portal/public controllers verify record ownership (IDOR prevention)
- [ ] Record rules include multi-company rule (global, no groups)

## Views / Frontend

- [ ] `<list>` not `<tree>`
- [ ] Expression syntax, not `attrs={}`
- [ ] `name` attribute on `<page>` and `<filter>`
- [ ] `<chatter/>` present when model inherits `mail.thread`
- [ ] No inline styles — use Bootstrap classes
- [ ] OWL uses current imports

## Mail / Tracking

- [ ] `tracking=True` on state/status fields
- [ ] Bulk operations use `tracking_disable=True`
- [ ] User-visible events use `message_post()`, not `_logger`
- [ ] `message_post()` is called on single records (`ensure_one()` contract)

## Module Structure

- [ ] Manifest `data` order: security → data → reports → views
- [ ] `noupdate="1"` on user-configurable records
- [ ] Module icon at `static/description/icon.png`

## Testing

- [ ] At least one success-path test
- [ ] At least one failure/validation test
- [ ] Batch behavior tested with multiple records when method supports multi-recordsets
- [ ] State transition assertions for workflows
- [ ] Security changes have access-scope tests
- [ ] Performance-sensitive code has query-count or batch-volume coverage/proof
- [ ] Transaction-sensitive code has resume/idempotency behavior documented or tested
