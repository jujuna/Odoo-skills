# AI Smells — code that looks generated

Patterns that agents produce and core developers do not: guards for things that cannot happen,
fallbacks for values that are always there, errors swallowed "to be safe", helpers that pass six
arguments around. Each one adds lines a reviewer must read and hides the real failure. The
design rules are in `simplicity.md`; this file is the statement-level catalog, with what to
write instead. Layout (line splits, docstrings, comments) is `compact-code.md`.

Measured on 2026-10-30 (`scripts/compact_scan.py --stats`), per 1000 lines:

| Code | `except Exception` | `hasattr(` |
|---|---|---|
| `addons/account/models` | 0.2 | 0.2 |
| `enterprise/hr_payroll/models` | 0.7 | 0.4 |
| `rs_einvoice` | 6.3 (48 in total) | 1.2 |
| `rs_waybill` | 8.4 | 1.9 |

---

## 0. The method: core first, then better

1. Find the core twin: the same job in `addons/` or `enterprise/` (an EDI send, a reversal, a
   cron over companies, a wizard confirm). The scout's precedent task does this
   (`dependencies.md`)
2. Write ours in the twin's shape: its hooks, its error boundary, its length
3. Deviate only when ours is **shorter, as clear and behaves the same**; say why in the review.
   Core is not perfect (it splits lines too, its docstrings run 4-5 lines): copy its
   structure, not its noise
4. Ours is clearly longer than the twin for the same job: something below is in it

## 1. Guarding what is always there

| Smell | Why it is wrong | Write |
|---|---|---|
| `hasattr(self, 'payment_state')` on `account.move` | the field is in `account`, which we depend on | `self.payment_state` |
| `hasattr(self.company_id, '_get_user_fiscal_lock_date')` | core method (`account/models/company.py:642`) | call it |
| `try: from zeep... except ImportError: return ()` | `zeep` is in `external_dependencies`: the module does not install without it | import at the top |
| `hasattr(Users, '_rs_responsible_user')`, method from a module not in `depends` | an undeclared dependency hidden behind a guard | add the module to `depends`, or drop the feature here |
| `self.display_name or self.name or '—'` on a posted or draft move | `display_name` is never empty there: "Draft Bill" for a draft, the number once posted (`account_move.py:5360`); only a cancelled move that never got a number has an empty one | `self.display_name` |
| `if records:` before `for r in records:` or before `records.write()` | both are no-ops on an empty recordset (`odoo/orm/models.py` `write()` returns early) | drop the `if` |

Real cases: `rs_einvoice/models/account_move_buyer.py:525`, `:879`;
`rs_soap_service.py:92` (`_zeep_fault_class`); `rs_einvoice_cron.py:145`
(`rs_base_methods` is not in `rs_einvoice` `depends`: decide which way, do not guard).

## 2. Swallowing errors

`except Exception` that logs and continues turns a bug (a typo, a missing field) into a warning
in a log nobody reads, and the user sees success.

Core's shape (`account_edi_proxy_client/models/account_edi_proxy_user.py:119`): the one method
that calls the external service catches the transport errors by name and raises one domain
error; callers catch only that error (`l10n_it_edi/models/account_move.py:1287`).

| Where | Write |
|---|---|
| The call to rs.ge, a bank, any SOAP/REST service | catch the library's errors by name (`zeep.exceptions.Fault`, `requests.exceptions.RequestException`) in the service class, raise `UserError` with one sentence |
| A button the user pressed | no `try`: let `UserError` reach the user, let a bug reach the traceback |
| A cron or batch loop that must go on to the next record | `except Exception: _logger.exception(...)` around one record, with a savepoint (`transactions.md` section 5) |
| Local work after an irreversible external call (rs.ge accepted, the bank sent) | a broad catch only so the record of that call survives a later failure, with a one-line comment saying so (`transactions.md`) |
| Anything else (a chatter post, an activity, a read) | no `try`: if it fails, the user must know |

Those two rows are the only places a broad catch belongs.

## 3. Silent defaults that hide bad data

```python
# BAD: a value that does not parse becomes 0 without a trace (used on rs.ge ids:
# account_move_seller.py:427, :523; rs_einvoice_cron.py:216)
def rs_to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Convert once at the boundary (the service method that reads the response) and let a bad value
fail there with the rs.ge call in the message. After the boundary, types are known: no
`hasattr(value, 'strftime')`, no `hasattr(op_dt, 'date')`, no `getattr(result, 'x', None)` on
an object whose schema we know.

## 4. Helpers that pass the world around

```python
# BAD: one caller, six positional arguments
new_draft = self._rs_reissue_create_draft(
    service, verify, correction_id_int, verify_status, v_k_type, correction_rs_id)
```

A private helper with one caller and more than three arguments is a piece cut out of a long
method, not a reusable step. Either keep the code inline (`simplicity.md` rule 3), or pass the
object that holds the values (the record, the response) and read them inside. Real case:
`account_move_buyer.py:560` calls `:650`, its only caller.

Same family:
- A method that only calls another one with the same arguments
- A function at module level that takes `self`-like arguments: make it a method
- A tuple used once on the next line (`paid_states = (...)`): put it inline

## 5. Re-doing what the ORM does

| Smell | Write |
|---|---|
| `recs.mapped('partner_id')`, `recs.mapped('line_ids.move_id')`: a path of **relational** fields | `recs.partner_id`, `recs.line_ids.move_id`: on several records a relational field returns the union, the same recordset `mapped()` returns (`odoo/orm/fields_relational.py:42`; core: `account_move.py:912` `self.statement_line_ids.statement_id.journal_id`) |
| — | Keep `mapped()` when the last field is **not relational** (`recs.mapped('name')` gives a list; `recs.name` on two records raises "Expected singleton", `odoo/orm/fields.py:1655`), when the path is in a variable, or with a function |
| `recs.filtered(lambda r: r.flag)` | `recs.filtered('flag')` |
| `hasattr(value, 'id')` to tell a record from a scalar | `self._fields[name].relational` |
| `len(recs) > 0`, `recs.ids and ...` | `if recs:` |
| `search([...]).ids` then `browse(ids)` | the search result is already the recordset |
| `[r.id for r in recs]` | `recs.ids` |
| Fetching then filtering in Python | put the condition in the domain |

## 6. Defending against ourselves

- Context flags that skip our own check (`rs_skip_lock_check`): every flag is a second code
  path to test. First ask whether the check sits in the right place (`simplicity.md` rule 8)
- The same check at the button, in the method and in `write()`: one, at the real boundary
- Re-reading a record we just wrote, to "make sure"
- `sudo()` added because a test failed, without a stated reason (`security.md`)

## 7. Review routine

1. `python .claude/skills/odoo-dev/scripts/compact_scan.py <module_dir>`: the hits for
   sections 1-2 and `compact-code.md`
2. For each hit: is the guarded thing guaranteed (field in a `depends` module, external
   dependency, computed for every record)? Then remove the guard
3. For each `except Exception`: is it the per-record catch of a cron? Otherwise name the errors
   or remove the `try`
4. Each private helper: callers (`dead_names.py` lists none, grep for one), argument count
5. Removing a guard, a fallback or a `try` can change behavior (an error now reaches the user).
   That is a behavior change: list it as one (`refactor.md` section 2), never hide it inside a
   cleanup
