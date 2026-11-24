# Quality Checklist — Odoo 19

Run this before returning any code. Every item is a real bug or a real review blocker.

---

## Hard Rules (check first — numbers match `SKILL.md` and `simplicity.md`)

- [ ] 1 What the request misses is in the answer: what core or a setting already does, the
      flows and cases it leaves out
- [ ] 2 Smallest change; no new model / wizard / menu / setting the task did not require
- [ ] 3 No helper with one caller hiding a few lines, no wrapper, no override that a field
      attribute or core hook could replace
- [ ] 4 Connections listed in the answer: callers and overrides of each changed method,
      views inheriting a changed view, `@api.depends` / `related` chains on a changed field,
      modules reading the same data, `db_refs.sql` for a renamed, removed or re-meant name,
      what existing records get at upgrade
- [ ] 5 Core precedent found and followed, in every place the change belongs; `super()` on
      the normal path; no core screen element hidden or replaced; no hand-made amount math
- [ ] 6 Nothing duplicated: no field, method, helper or screen that already exists in the
      module, its `depends` or core
- [ ] 7 No rate, amount, limit, date, account, tax, journal, record id or name literal in
      logic; technical constants named once
- [ ] 8 Every new `raise` / constraint / `required=True` / guard was asked for or approved
- [ ] 9 Every behavior claim backed by a source line, a `SELECT`, or a test run
- [ ] 11 No statement split that fits in 120 characters; imports one line or one name per
      line; no module or `_inherit` class docstring; method docstrings only for a why (one
      line, three at most); no narrating comments, dead or commented-out code, unused imports;
      user errors one sentence; no `hasattr` / `or` fallback / `except Exception` guarding what
      is always there (`scripts/compact_scan.py <changed files>` is clean for lines you wrote)
- [ ] 12 No migration script; `version` untouched; no unrequested README, tests or docs
- [ ] 13 Plain on screen: labels, buttons, messages, and errors use business words (no field names or Odoo jargon); errors state what happened and what to do next in one sentence; `ka_GE.po` updated for changed/new texts
- [ ] 14 Readable and easy to change: clear names, one job per method (~40 lines max per helper), normal path top to bottom, each rule in one place
- [ ] 15 Untouched code below our standard in opened files reported separately as a proposal — never silently edited outside the task

Rule 10 is the Multi-company and Security sections below.

## Multi-company (`multicompany.md`)

- [ ] `company_id` exists, `index=True`, defaults to `self.env.company`
- [ ] A global `ir.rule` (no `groups`) scopes the model to `company_ids`
- [ ] `check_company=True` on every company-scoped relational field
- [ ] `_check_company_auto = True` when any field uses `check_company`
- [ ] `_check_company_domain` overridden when branches must inherit the record
- [ ] No `self.env.user.company_id` in business logic
- [ ] Mixed-company loops use `grouped('company_id')` + `with_company()`
- [ ] Every `sudo()` on a scoped model re-applies the company filter

## Security (`security.md`)

- [ ] `security/<module>_security.xml` is **first** in manifest `data`, `ir.model.access.csv` right after it
- [ ] Header is `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`
- [ ] `model_id:id` holds the `model_` xml id; no ACL row with an empty `group_id:id`
- [ ] Every new model has at least one ACL row, or nobody can use it
- [ ] Group rules come in sets: a manager `[(1, '=', 1)]` rule beside a user's own-records rule
- [ ] Wizards restricted by an `ir.rule` `[('create_uid', '=', user.id)]`
- [ ] Child models repeat the parent's rule domain through the many2one (`order_id.partner_id`)
- [ ] Sensitive fields carry `groups=` (or `fields.NO_ACCESS` for internal-only fields); sensitive `related=` chains set `related_sudo=False`; restricted models set `_allow_sudo_commands = False`; internal methods use `@api.private`
- [ ] Every `sudo()` has a permission check before it and a one-line reason
- [ ] Portal/public routes verify ownership and return 404 on mismatch; webhooks reading `request.env` use `auth='public'` (never `auth='none'`); secrets compared with `consteq()` / `hmac.compare_digest`
- [ ] Downloads use `content_disposition()`, local files use `file_open()`, HTML interpolation uses `Markup.format()`, outbound HTTP passes explicit `timeout=` with TLS verification enabled
- [ ] No SQL built by string interpolation; re-raised exceptions chained (`raise ... from err`); no `assert` for runtime validation

## Python / ORM

- [ ] New model has `_description`
- [ ] Methods are batch-safe; no accidental singleton assumptions
- [ ] `ensure_one()` only where one record is truly required
- [ ] `create()` overrides use `@api.model_create_multi` and call `super()` once
- [ ] `write()` / `unlink()` overrides validate in batch, one `super()` call
- [ ] No deprecated APIs: `check_access_rights`/`_rule`, `_filter_access_rules`,
      `_check_recursion`, `toggle_active`, `self._cr`/`_uid`/`_context`, `name_get`,
      `type='json'`, `read_group()` (`_read_group` / `formatted_read_group`)
- [ ] No v20-only API (`guardrails.md` §13): no `ir.access`, `compute_sql`, `get_str`,
      `api.ormcache`, `user_writeable`, `BinaryBytes`, OWL 3 `proxy`/`useProps`
- [ ] No N+1 queries in compute or business methods
- [ ] Sync / upsert loops write only rows that changed and group identical values; one `create()` for new rows (`performance.md` §6)
- [ ] Lock the parent before creating its children; `try_lock_for_update(allow_referencing=True)` unless the key changes (`transactions.md` §10)
- [ ] Multi-record crons commit per record with `_commit_progress` (`transactions.md` §10)
- [ ] No `ondelete='cascade'` from history / audit rows to a deletable parent (`orm.md` §9)
- [ ] User-facing date defaults use `fields.Date.context_today`, not `fields.Date.today` (`guardrails.md` §7)
- [ ] A `date` compared with a Datetime field is widened to the user's local day (`orm.md` §4)
- [ ] Computes assign every record and never write to other models
- [ ] Dynamic domains use `odoo.fields.Domain`
- [ ] x2many updates use `odoo.Command`
- [ ] User-facing text uses `self.env._()` with `%s`; no f-strings inside it
- [ ] Module-level helpers take `env` and call `env._()`; module-level constants use `_lt`
- [ ] `@api.constrains` methods raise `ValidationError`, not `UserError`
- [ ] A chatter/log entry written just before a `raise` uses its own cursor when it must
      survive the rollback (`transactions.md` section 9)
- [ ] Row locks use `lock_for_update()`; catch `LockError` when the user needs a specific message
- [ ] `_logger` uses lazy `%s` formatting
- [ ] Raw SQL parameterized; cache invalidated after SQL writes; `modified()` called
- [ ] Float comparisons use `float_compare` / `float_is_zero`
- [ ] Delete restrictions use `@api.ondelete`
- [ ] No mutable default arguments
- [ ] Constraints and indexes are `models.Constraint(...)` / `models.Index(...)`
- [ ] `cr.commit()` only in resumable cron/import code, with a test guard

## Cron (`cron.md`)

- [ ] Cron XML has no `numbercall` / `doall` (removed; install fails) and sets `user_id`
- [ ] The job does not depend on its Scheduler User being superuser; `sudo()` and company
      filtering are explicit
- [ ] Work done with a user's own credentials or language runs under `with_user(user)`
- [ ] A cron that notifies (activity, message, mail) stores a marker such as
      `..._escalated_at`, so the next run does not repeat it
- [ ] Cron method names stay stable (`code` sits in a `noupdate` record in the database)

## Fields

- [ ] `Monetary` paired with a `currency_id` + `currency_field=`
- [ ] `fields.Date.today` / `Datetime.now` defaults are callable (no parentheses)
- [ ] Every `Many2one` sets `ondelete`
- [ ] Non-stored computed field that must be searched uses a `search=` method; `store=True`
      only when it must be grouped or sorted
- [ ] Self-referential computes declare `recursive=True`
- [ ] `@api.onchange` is UX-only; real logic is in a `@api.depends` compute
- [ ] `copy=False` on sequences, states, unique references
- [ ] Quantities rounded with `decimal.precision` 'Product Unit' (`uom.rounding` is only a
      compute alias of it)

## Views / frontend

- [ ] `<list>`, expression syntax, `name=` on `<page>` and `<filter>`
- [ ] `<chatter/>` when the model inherits `mail.thread`
- [ ] `t-out` preferred over `t-esc` in new templates (both work in v19)
- [ ] `t-call` parameters passed as attributes (`x="expr"`, `x.f="text"`) in new code
- [ ] OWL 2: `useState()` for reactive state; `static props` declared; `useEffect(fn, () => deps)`
- [ ] OWL 2: refs via `useRef("x")` + `t-ref="x"`, read as `ref.el`; `t-key` on every `t-foreach`
- [ ] xpaths into core OWL templates tested against the current core template
- [ ] Icons: Font Awesome (`fa fa-x`, `icon="fa-x"`); every icon-only `<i>` has a `title`
- [ ] No inline styles — Bootstrap classes
- [ ] SCSS: no hard-coded neutral colours — `$o-view-background-color`, `$o-gray-*`,
      `$o-main-text-color`; own colours that need a dark shade hold both values via
      `if($o-webclient-color-scheme == dark, dark, light)` (`owl.md` → Dark mode)
- [ ] `web.dark_mode_variables` `before` targets live in `web._assets_primary_variables`,
      not `web.assets_backend` (else the lazy dark bundle 500s)

## Mail / tracking

- [ ] `tracking=True` on state/status fields
- [ ] Bulk operations run with `tracking_disable=True`
- [ ] User-visible events use `message_post()`, not `_logger`
- [ ] `message_post()` called per record (singleton contract)

## Module structure

- [ ] Manifest order: groups → `ir.model.access.csv` → data → reports/wizards → views/menus
- [ ] `noupdate="1"` on records the user is expected to edit
- [ ] Module icon at `static/description/icon.png`
- [ ] `depends` is the smallest set that works

## Refactor / quality review (`refactor.md`)

- [ ] Findings sorted into behavior change vs cleanup; only cleanup goes into the refactor
- [ ] `code_inventory.py compare`: no translatable text removed or added unless intended
- [ ] No public name renamed; nothing deleted before `dead_names.py` and its DB check
- [ ] External requests recorded old vs new and identical (`oldnew.Recorder`)
- [ ] Intended differences listed in the report; deploy note and `git add -A` hint given

## Tests

- [ ] Tests were **asked about**, not assumed
- [ ] If written: one success path, one failure/permission path
- [ ] If written: batch behavior covered when the method is multi-record
- [ ] If written: access-scope assertions for security-sensitive changes
