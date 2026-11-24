# Compact Code — lines, imports, docstrings, comments, messages

How our code is laid out on the page. Applies to every line we write or change. Logic that is
longer than it needs to be is `ai-smells.md`; fix that first, because shorter logic is what
makes most split lines fit on one.

Measured on the odoo19 tree 2026-10-31 (`scripts/compact_scan.py --stats`), statements written over several
lines that fit in 120 characters when joined, per 1000 lines:

| Code | Needless splits / kloc | Methods with a docstring | Module docstrings |
|---|---|---|---|
| `addons/account/models` | 10 | 30% | 0 of 54 files |
| `addons/stock/models` | 8 | 21% | 0 of 25 |
| `enterprise/account_reports/models` | 7 | 30% | 0 of 40 |
| `rs_einvoice` | 34 | 72% | 4 of 19 |

The cause: the writer wraps at 79-88 characters (PEP 8 / black habit) while Odoo has no line
limit (`ruff.toml` ignores `E501`; `account_edi_proxy_user.py:119` is one 165-character line).

---

## 1. One statement, one line — up to 120 characters

A statement stays on one line when it fits in **120 characters including indentation**. Split
only above that.

```python
# BAD: 4 lines for a 98-character call
pending = original._rs_find_pending_correction_blocker(
    exclude_move=self,
)

# GOOD
pending = original._rs_find_pending_correction_blocker(exclude_move=self)
```

```python
# BAD
if (self.env.context.get('rs_skip_lock_check')
        or not self.rs_einv_id or self.rs_einv_skip):
    return

# GOOD
if self.env.context.get('rs_skip_lock_check') or not self.rs_einv_id or self.rs_einv_skip:
    return
```

```python
# BAD
raise UserError(_(
    "Accept on rs.ge only applies to vendor bills and vendor credit notes."
))

# GOOD (105 characters at its real indentation)
raise UserError(self.env._("Accept on rs.ge only applies to vendor bills and vendor credit notes."))
```

- No trailing comma after the last argument of a call that fits on one line: formatters read
  it as "keep this exploded" (`exclude_move=self,`)
- No backslash continuation. A conditional expression too long for one line becomes an
  `if` block or loses its guard (`ai-smells.md` section 1)
- A list, dict or domain literal that fits stays on one line too
- JS: 100 characters, not 120. Odoo's prettier config is `printWidth: 100`
  (`addons/web/tooling/_eslintrc.json:17`); a longer join is split again by the next format run

## 2. Over 120: shorten first, then split

Most long lines are long because the code is. Before splitting, try in this order:

1. Shorter expression: field access instead of `mapped()` when every field in the path is
   relational (`ai-smells.md` section 5), the string form of `filtered()`, no default
   arguments repeated
2. Fewer arguments: pass the record, not five of its fields (`ai-smells.md` section 4)
3. A local variable for a value used twice, or for a sub-expression that has a business name

```python
# BAD: 3 lines
originals_to_refresh = rs_tracked_cns.mapped('reversed_entry_id').filtered(
    lambda original: original.rs_einv_id
)

# GOOD: same records, one line (reversed_entry_id is a many2one, so field access on several
# credit notes returns the union, as mapped() does)
originals = rs_tracked_cns.reversed_entry_id.filtered('rs_einv_id')
```

Still over 120: split the way core does.

```python
# Arguments fit on one continuation line
move_vals = self._prepare_move_vals(
    journal, partner, date, currency, ref=ref, narration=narration, auto_post='no')

# They do not: one per line, trailing comma, closing bracket on its own line
blockers.append(self.env._(
    "Original bill %(name)s is on or before the lock date (%(lock)s).",
    name=self.display_name,
    lock=lock_date,
))

# Long condition: break before `and` / `or`, inside parentheses
if (move.move_type in ('in_invoice', 'in_refund')
        and move.state == 'posted' and not move.rs_einv_id):
```

Never split one logical part across lines (half a keyword argument, a domain tuple over two
lines).

## 3. Imports

One line when the names fit in 120 characters. Otherwise one name per line with a trailing
comma, the way `addons/account/models/account_move.py:24` imports from `odoo.tools`. Never two
or three names per line.

```python
# BAD
from .account_move import (
    _rs_status_label, rs_to_int, rs_to_float,
    RS_DRAFT_OR_NEW_CORRECTION, RS_ACCEPTED,
)

# GOOD (107 characters)
from .account_move import RS_ACCEPTED, RS_DRAFT_OR_NEW_CORRECTION, _rs_status_label, rs_to_float, rs_to_int
```

Order: standard library, third party, `odoo`, `odoo.addons`, local (`ruff.toml` `[lint.isort]`).
No unused import, no import inside a method (`python.md` section on imports).

## 4. Docstrings — default none

Core puts a docstring on 20-30% of methods and on no model file. The rest have a name that
says what they do. We follow that.

| Where | Rule |
|---|---|
| Module (top of a `.py` file) | Never. The file name says what it holds; `README_DEV.md` maps the files. Exception: a standalone script that prints `__doc__` as its usage (`sys.exit(__doc__)`) |
| Class with `_inherit` | Never. `_description` names a new model |
| Method | Only when it says something the name, signature and body do not: the business reason, what the return value means to callers, a side effect, a gotcha. One line; up to three only for a business rule |
| Test method | Only when the name cannot say which case it covers |

```python
# BAD: module docstring
"""Cancelling and reversing a document after rs.ge voided or superseded it: the automatic
reversal, the manual-reversal flag and activity, and the correction reset after a rejection."""

# BAD: retells the body line by line
def _rs_pull_apply_header(self, result, status):
    """Store status, series and number, move a draft's date to the rs.ge operation date (a
    posted bill only gets a warning), and take the correction type when none was chosen."""

# GOOD: none, the name and 10 lines of body say it
def _rs_pull_apply_header(self, result, status):

# GOOD: the one thing a caller cannot see
def _rs_schedule_manual_reversal_activity(self, reason='', note=None):
    """Crons run as OdooBot, so the activity goes to the company's RS responsible user."""
```

- No `Args:` / `Returns:` / `Raises:` blocks, no step lists, no restating the method name
- The docstring line obeys section 1: 120 characters
- JS: the same rule for `/** ... */`

## 5. Comments — almost never

An inline comment (`#`, `//`, `<!-- -->`) earns its place only for one line whose reason the
code cannot show: a workaround with its cause, a framework gotcha, a security or transaction
reason.

| Never | Why |
|---|---|
| A comment that narrates the next line (`# loop over the moves`) | the code says it |
| Section banners (`# ---- helpers ----`, `# ======`) | the file is short enough, or split it |
| Plan or ticket ids (`# W3 fix`, `# F7`, `# per review 10-26`) | history belongs in git and the plan file |
| Commented-out code, `TODO` without an owner and a reason | dead text |
| `/** @odoo-module **/` in a file under `static/src` or `static/tests` | dead text: those files are modules anyway (`odoo/tools/js_transpiler.py:725`); 1 of 209 files in `web/static/src/core` has it |
| A comment repeating the docstring | say it once |

## 6. Messages — one sentence

**User errors** (`UserError`, `ValidationError`): one sentence that says what is wrong and
what to do. No "What to do:" sections, no paragraphs, no explaining our internals.

```python
# BAD
raise UserError(_(
    "This bill is already %(state)s and has reconciled payment(s). "
    "Reject on rs.ge would invite a reversal that drives AP "
    "negative.\n\n"
    "What to do:\n"
    ...

# GOOD
raise UserError(self.env._("Unreconcile the payments of %s before rejecting it on rs.ge.", self.display_name))
```

**Georgian translation — every time an error or validation text changes.** Odoo finds the
Georgian text by the exact English text (`odoo/tools/translate.py:1861`, keyed per addon). Change
one word of a `UserError`, `ValidationError`, `_()` / `self.env._()` / `_lt()` / JS `_t()` text
and Georgian users see English until the `.po` matches. In the same change:

1. Open the module's `i18n/ka_GE.po` (`bsc_strategy`, `bpmn_process_management`: `ka.po`)
2. Changed text: set `msgid` to the new English exactly, and fix the `msgstr` to match. Start from
   the Georgian that is there (it may be tester-approved wording): change only what the English
   change needs, keep the module's terms, keep every placeholder (`%s`, `%(name)s`) with the same
   names and count. Writing new Georgian: use plain business Georgian matching existing terms in the same module or Odoo core (`ka_GE.po`)
3. New text: add an entry with the Georgian `msgstr`. Removed text: delete its entry
4. Check (Python texts; JS `_t()` by hand): `code_inventory.py snapshot <module> --rev HEAD
   -o before.json`, `snapshot <module> -o after.json`, `compare before.json after.json`. Every
   changed or new text must show as translated in `ka_GE.po`
5. Report it: "ka_GE.po updated: N entries". Python and JS texts are read from the `.po` file
   when the server starts, so a restart shows them; field labels, selections and view texts are
   stored in the database and need `-u <module>` (with `--i18n-overwrite` when a Georgian value
   is already there; it also replaces Georgian edited in the UI)

Joining a text written over several lines into one string (same words, same spaces) keeps the
`msgid` and needs no `.po` change. Rewording, a fixed typo or a new placeholder always does.

**Log lines**: one line, lazy arguments (`_logger.warning("... %s", x)`, never `%` or an f-string
inside the call), the record id and the failing call, nothing else. `_logger.exception` already
prints the traceback: do not add `e` to the text.

**Chatter** (`message_post`): one short sentence or a two-column table; no narration of what
the code did step by step.

## 7. Applying it

- New code: written this way from the start
- A changed or new user text: its `i18n/ka_GE.po` entry in the same change (section 6)
- Existing code: only the lines you change, unless the task is a cleanup. A cleanup is a
  refactor (`refactor.md`): its own phase, no behavior change, proven with `oldnew.py`
- Find candidates: `python .claude/skills/odoo-dev/scripts/compact_scan.py <module_dir>`
  lists needless splits, module docstrings, docstrings over three lines and the
  `ai-smells.md` patterns, each with path:line
