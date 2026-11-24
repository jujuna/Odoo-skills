# Simplicity Law — Odoo 19

The detail behind the 12 Hard Rules in `SKILL.md`: section N explains rule N. Ranked above
every other reference file. If `orm.md`, `sql.md`, `scaffold.md` or any other file shows a
pattern that breaks a rule here, this file wins.

The goal of a task is **the smallest correct change that a user and a developer both
understand on first read**. Not the most complete solution, not the most defensive one.
Short never beats correct.

---

## 1. Say what the request misses

The request is the user's view of the problem. Before planning, check it, and put what
matters first in the reply, one line each, biggest first:

| Question | Where to look |
|---|---|
| Does core or a setting already do this? | the app's settings, the same feature in `addons/` / `enterprise/`, `documentations/<module>.md` |
| Which flows and modules produce or read what this changes? | `coupling-map.md`, the flow sweep (rule 4) |
| Which cases does it leave out? | other companies and branches, cancel / reset to draft / refund / reverse, records that already exist, another currency, import, cron, portal, archived records |
| Does it fix the symptom or the cause? | trace where the wrong value comes from before changing where it shows |
| Is there a simpler way to the same result? | rules 2 and 3 |

A finding that changes the plan is said before any code. A finding that needs the user's
decision is a question: the risk in one line and your recommendation. Nothing found: say
nothing, do not pad the answer with what you checked.

## 2. Smallest change that works

Take the highest option that solves the task:

1. Configuration or an existing field — no code
2. A field or view attribute: `related=`, `compute=` with `@api.depends`, `default=`,
   `domain=`, `readonly` / `invisible` / `required` in the view
3. Extend an existing method through its hook (`_prepare_*`, `_get_*`, `_compute_*`) with
   `super()`
4. A new field or method on an existing model
5. A new model, wizard or view ← state the reason
6. A new module ← state the reason

A new model is a permanent cost for the user: a menu, access rows, records to maintain.
Never add a model, wizard, menu or setting the task did not require.

## 3. No over-engineering

- Solve the case in front of you, not an imagined future one
- No helper for one caller when the inline code is a few lines; no method that only calls
  another one
- No abstraction layer, mixin, hook or generic engine for a single use
- No override where a field attribute, a compute dependency or a core hook does the job
- One override of a method per module; extend that one instead of adding a second
- If the simple version fails only in a case that cannot happen in this database, ship it
  and name the case

## 4. Find the connections

A change has two directions. Check both before writing it and put the result in the answer
(format: `dependencies.md` → Reporting format).

| Direction | Questions |
|---|---|
| What reaches it | who calls it, who overrides it, which views inherit it, which modules read the same data (`coupling-map.md`), which code stored in the database uses its name (`scripts/db_refs.sql`) |
| What it reaches | which fields recompute (`@api.depends` and `related=` chains on it), which reports, declarations, exports and bank files read it, what existing records get at upgrade (`dependencies.md` → Downstream) |

Size it to the change: two greps for our own code (Tier 1), the full core sweep for a core
override (Tier 2), a flow sweep when a business object changes meaning (Tier 4). It exists
to catch the one connection you did not know about, not to justify an audit.

## 5. Respect core logic — and its numbers

Before inventing anything, find the same thing in `addons/` or `enterprise/` and copy it.
Matching core is what keeps our code working across upgrades.

- Naming: `action_*` for buttons, `_compute_*`, `_prepare_*`, `_get_*`, `_check_*`
- Wizard = `TransientModel` with one `action_*` confirm method; status = a `Selection`
  `state` field, not booleans
- `super()` on the normal path; change the shortest branch; never re-implement a method you
  extend
- Reuse standard flows (journal entries, payments, stock moves); never hand-write GL, never
  bypass the ORM to shortcut a standard flow
- Core shows a misleading number, card or line on our data: do not override, hide or replace
  it; add our own element beside it and document the core behavior
- A change that belongs in several places copies how core keeps them consistent (a shared
  mixin, the same method name on both models)
- No precedent anywhere in `addons/` or `enterprise/`: say so and reconsider the design

**Trust Odoo's numbers** (user rule, 2026-10-16). Odoo already computes taxes and their
base (`tax_base_amount`), residuals, payment amounts (the Pay dialog sums the lines it is
given), payment state and rounding.

- Never re-compute an amount Odoo stores or computes: read the field
- Never add, subtract or net amounts by hand to correct what Odoo shows: give Odoo the right
  lines (for example the bill's tax line and its credit note's tax line in one Pay dialog)
- Odoo's number looks wrong for our case: first find the input we gave it wrong; override a
  core compute only as a last resort, with the reason in the docstring
- Hand-written arithmetic only where no Odoo field holds the value (a declaration's monthly
  share), in one place

If the solution looks strange or clever, it is wrong. Find the boring Odoo equivalent.

## 6. Reuse, never duplicate

Search before you write: the module, its `depends`, our shared bases (`gec_bank`,
`rs_base_methods`) and core. The scout's Reuse task (`odoo-scout.md`) does this.

| About to write | Use instead |
|---|---|
| A field holding a value another record already has | `related='x.y'`; `store=True` only to search or group |
| A method doing what one in this module or a dependency does | call it; extend it with `super()` when it needs one more key |
| The same 3+ lines in a second place | one helper, in the module both places depend on |
| The same dict or domain built in several methods | one `_get_*` / `_prepare_*` helper, named the way core names them |
| A second model for data that belongs on an existing one | fields on the existing model |
| A second screen to finish one business action | the button, field or smart button on the record the user is already on |

A helper earns its place by removing a copy or by naming a step a long method needs. A
helper used once to hide three lines does not (rule 3).

## 7. No fixed business values in code

A value the business or the law can change must change without a code change. Read it from
the record that owns it:

| Value | Read it from | Never |
|---|---|---|
| A rate, amount, limit or threshold | a field on the record it belongs to (tax, company, journal, product); a payroll rate: an `hr.rule.parameter` with dated values, read with `payslip._rule_parameter(code)` (`enterprise/hr_payroll/models/hr_payslip.py:973`, data example `enterprise/l10n_in_hr_payroll/data/hr_rule_parameters_data.xml`) | `amount > 1000`, `* 0.02`, `RATE = 0.2` |
| A specific account, tax, journal, group, partner or product | its xmlid: `env.ref(xmlid, raise_if_not_found=False)`, for chart data `env['account.chart.template'].with_company(c).ref(xmlid)`; or a field or flag that marks it | a database id, a search by name, code or rate |
| A per-company choice users really change | a `res.company` field shown in Settings through a `related` field on `res.config.settings` (core: `po_double_validation_amount`, `addons/purchase/models/res_company.py:22`, read in `purchase_order.py:1251`) | a new model, a hardcoded default |
| A default for new records | `default=` on the field, or a `noupdate="1"` data record the user can edit | values forced inside `create()` |
| A technical constant that changes only with the code: selection states, field names, an external API's element names | one named module constant, a `tuple` or `frozenset` | the same literal repeated in several methods |

Real cases in our code:
- `geo_payroll/data/payroll_structure_data.xml`: the 2% pension rate is written 12 times in
  salary rule code across 4 structures, inside `noupdate="1"`. A rate change means 12 edits,
  and the upgrade does not even reach existing databases.
- `rs_einvoice/models/account_move_sync.py:663` `_rs_get_purchase_vat_18`: finds the VAT by
  `amount = 18.0` with `limit=1`; its own TODO says the rate is hardcoded, and which tax it
  returns depends on sequence and id order (`coupling-map.md` T9).

Do not over-correct into rule 3: no settings screen for a value nobody will change. Business
data goes to an existing field first, a `noupdate` record second, a new company field only
when users must change it per company.

## 8. No validation nobody asked for

- Prefer making the wrong value impossible: a `domain`, `readonly`, a default, a selection
- A new `raise`, `@api.constrains`, `models.Constraint`, `required=True` or guard branch the
  task did not ask for is a **proposal**, not code: one line in the answer — the bad case it
  blocks, a real example, your recommendation — and the user decides
- Once agreed: one clear error at the real boundary (confirm / post / send), not on every
  write; never two checks that fail on the same bad input
- Never raise on something the user can see and fix themselves; no warning popup for normal
  work, no confirmation dialog on a reversible action
- Error text: one sentence that says what to do next, in `self.env._()`
- Not covered by this rule: what core already enforces (keep `super()`), access rights and
  `check_company` (rule 10)

## 9. Proof, never guessing

Every claim about Odoo behavior is backed by one of:

- a source file + line you actually read
- a `psql SELECT` result
- a test run output

If none exists, say so in plain words: *"not verified — this is my assumption."* Never
present an inferred field name, method name or flow as fact. Never invent a field, method,
module or option you have not seen in the source.

## 10. Multi-company and access are part of "correct"

A model holding business data without `company_id`, without `check_company=True` on its
scoped relations and without a multi-company record rule is not a simpler solution — it is a
broken one. A model without `ir.model.access.csv` rows cannot be used by anyone. Details:
`multicompany.md`, `security.md`.

## 11. Compact code: one line, few docstrings, no comments

```python
# GOOD: the docstring says the one thing the name cannot
def _prepare_invoice_values(self):
    """Use the order's fiscal position, so a later partner change does not re-tax the invoice."""

# GOOD: no docstring, the name says it all
def action_draft(self):
    self.write({'state': 'draft'})

# BAD: an essay that restates the name and walks through the body
def _prepare_invoice_values(self):
    """
    This method prepares and returns the dictionary of values that will later be used
    to create the customer invoice for the current order. First it checks that...
    """
```

- One statement per line up to 120 characters; shorten before splitting
- No module docstrings, no docstrings on `_inherit` classes; a method docstring only for a
  why, a business rule or a gotcha: one line, three at most
- Inline comments only for one genuinely non-obvious line; no banners, plan ids or
  commented-out code
- No guard for what a dependency guarantees, no `except Exception` outside a cron's
  per-record loop or the record of an irreversible external call
- Never touch lines, comments, docstrings or type hints in code you did not change

Details and real cases: `compact-code.md` (layout and text), `ai-smells.md` (logic).

## 12. Never do these

| Do not | Instead |
|---|---|
| Write a migration script | solve it in code: a compute, a default, a fill-only-if-empty pass in the install or upgrade path |
| Bump `version` in `__manifest__.py` | leave it, the user decides releases (a `19.0.` prefix: flag it) |
| Add tests, a `README` or module docs on your own | ask first, say what you would cover |
| Add a model, wizard, menu or setting nobody asked for | extend what exists (rule 2) |
| Rewrite or correct a core method or screen | `super()` and the existing hook, or our element beside it (rule 5) |
| Compute an amount Odoo already has, or net amounts by hand | read Odoo's field, give Odoo the right lines (rule 5) |
| Duplicate a field's data or a method's logic | `related=`, call the existing method (rule 6) |
| Put a rate, account, tax, id or name in code | read it from the record that owns it (rule 7) |
| Add a validation "just in case" | propose it, the user decides (rule 8) |
| Hand the user SQL or shell steps for their servers | a fix in module code, proven on a new and on an existing database |
