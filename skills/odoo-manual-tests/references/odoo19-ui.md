# Odoo 19 screen names (verified)

Core Odoo labels that checklists use again and again. Verified against Odoo 19 source on 2026-10-31
(`odoo/addons`, `addons`, `enterprise`). Anything not listed here must be looked up in the module
or in `addons/` before it goes into a checklist.

## Navigation

| Tester sees | Where | Source |
|---|---|---|
| Grid icon (all apps) | Top left corner | web client |
| Accounting › Customers › Invoices / Credit Notes / Payments / Products / Customers | Accounting app menus (root is "Invoicing" without `accountant`) | `account/views/account_menuitem.xml`, `accountant/data/account_accountant_data.xml` |
| Accounting › Vendors › Bills / Refunds / Payments / Products / Vendors | Accounting app menus | `account/views/account_menuitem.xml` |
| Accounting › Configuration › Accounting › Currencies / Journals / Taxes | Note the second "Accounting" | `account/views/account_menuitem.xml` |
| Settings › Users & Companies › Users / Companies / Groups | Settings app; Groups needs developer mode | `base/views/base_menus.xml`, `res_groups_views.xml` |
| Settings › Technical › Automation › Scheduled Actions | Needs developer mode: add `?debug=1` to the address | `base/views/base_menus.xml`, `ir_cron_views.xml` |
| Sales › Orders › Quotations / Orders / Customers | Sales app | `sale/views/sale_menus.xml` |
| My Preferences, Log out | User menu (avatar, top right) | `web/static/src/webclient/user_menu/user_menu_items.js` |

Live menu paths of any module, on the database the prompt names (the inventory script runs this with `--db`):

```sql
WITH RECURSIVE m AS (
  SELECT id, parent_id, (name->>'en_US')::text AS path FROM ir_ui_menu WHERE parent_id IS NULL AND active
  UNION ALL
  SELECT c.id, c.parent_id, m.path || ' > ' || (c.name->>'en_US') FROM ir_ui_menu c JOIN m ON c.parent_id = m.id WHERE c.active)
SELECT m.path FROM m JOIN ir_model_data d ON d.model = 'ir.ui.menu' AND d.res_id = m.id WHERE d.module = '<module>';
```

## Form controls

| Tester sees | Meaning | Source |
|---|---|---|
| Gear icon › Duplicate / Delete | Next to the record name at the top | `web/.../form/form_controller.js` |
| Cloud icon / X icon | Save / discard unsaved changes, next to the record name | `web/.../form/form_status_indicator/form_status_indicator.xml` |
| Status words top right, e.g. Draft › Posted | The record's state; current one highlighted | statusbar widget |
| Diagonal corner ribbon | `web_ribbon` widget: Paid, In Payment, Reversed on invoices | `account/views/account_move_views.xml` |
| Small boxes top right of the page | Smart buttons (`oe_stat_button`), open linked records | view XML |
| Pop-up window | Errors (UserError / ValidationError) and `confirm="…"` questions | web client |
| [Ok] / [Cancel] | Buttons of a `confirm="…"` question (title "Confirmation"), unless the button sets `confirm-label` / `cancel-label` | `web/.../confirmation_dialog.js`, `view_button_hook.js` |
| [Delete] / [No, keep it] | Buttons of the gear-menu Delete question (title "Bye-bye, record!") | `web/.../views/view_hook.js` |
| Small message top right that fades | Notifications (`display_notification`) | web client |
| Chatter | Messages and To-Do activities, right side (or under the form on small screens) | mail |
| Object buttons save first | Clicking any button saves the form before the button runs: a value typed just before a failing button stays saved | `form_controller.js` `beforeExecuteActionButton` |

## Invoices and bills (`account.move` form)

| Tester sees | Notes | Source |
|---|---|---|
| [Confirm] | Posts an invoice or bill (entries use [Post]) | `account_move_views.xml` header |
| [Reset to Draft], [Cancel] | Cancel only shows on drafts | same |
| [Credit Note] | Opens the reversal window on posted invoices/bills | same |
| [Pay] › [Create Payment] | Register payment (several: [Create Payments]) | `account_payment_register_views.xml` |
| [Send], [Print], [Preview] | Customer invoices | same |
| Customer / Vendor, Invoice Date / Bill Date | Field labels change with the document type | same |
| Tabs Invoice Lines, Other Info | Module tabs are added after Other Info | same |
| Add a line | Link under the invoice lines | same |
| Total | Bottom right of tab Invoice Lines | tax totals widget |
| Unreconcile | Payment info icon next to a paid amount › [Unreconcile] | `account/static/src/components/account_payment_field/account_payment.xml` |

Credit note window (`account.move.reversal`): fields "Reason displayed on Credit Note", "Journal",
"Reversal date"; buttons [Reverse] and [Reverse and Create Invoice]
(`account/wizard/account_move_reversal_view.xml`). Modules can add fields and hide buttons here.

Vendor bill warning window "Confirm Entries" appears on [Confirm] only when a draft *bill* has an
abnormal amount/date compared with 10+ earlier bills of the same vendor
(`_compute_abnormal_warnings`); fresh test vendors never trigger it.

## Sales

| Tester sees | Notes | Source |
|---|---|---|
| Sales order [Confirm] | Quotation → order | `sale/views/sale_order_views.xml` |
| [Create Invoice] › "Regular invoice" / "Down payment (percentage)" / "Down payment (fixed amount)" › [Create Draft] | Opens the new invoice | `sale/wizard/sale_make_invoice_advance*.py/xml` |
| Line links: quotation tab Order Lines › "Add a product"; RFQ tab Products › "Add a product"; invoice tab Invoice Lines › "Add a line" | Two different spellings | `sale_order_views.xml`, `purchase_views.xml`, `account_move_views.xml` |
| Deleting drafts: quotation gear › Delete works in Draft; an RFQ needs [Cancel] first ("In order to delete a purchase order, you must cancel it first.") | | `sale_order.py`, `purchase_order.py` |

## Payments, withholding, entries

| Tester sees | Notes | Source |
|---|---|---|
| Pay window checkbox "Withhold Tax Amounts", tab "Withholding" (columns Sequence Number with a grey placeholder number, Withholding base, Tax, Withholding amount), "Net Amount", [Create Payment] | Only when one payment is made; several bills need Group Payments | `l10n_account_withholding_tax/wizards/account_payment_register_views.xml`, `account_payment_register.py` |
| Bill smart box "Payments"; payment checkbox "Withhold Tax Amounts" and tab "Withholding" (Sequence Number, Tax, Withheld Amount) | | `account/views/account_move_views.xml`, `l10n_account_withholding_tax/views/account_payment_views.xml` |
| Payment [Reset to Draft] › [Cancel] → status "Canceled" (one l); invoices/entries "Cancelled" | | `account_payment.py`, `account_payment_view.xml`, `account_move.py` |
| Journal entries: [Post], [Reset to Draft], [Cancel Entry], tab Journal Items (Account, Label, Debit, Credit) | Journal Items also shows on draft invoices/bills | `account_move_views.xml` |
| Ribbon "In Payment" on a bill paid through an outstanding account (accountant installed) | "Paid" once matched with the bank | `accountant/models/account_move.py` `_get_invoice_in_payment_state` |
| Required field left empty in a form or wizard: red "Missing required fields" notification, field outlined red; numeric fields at 0 are never "missing" | So a server check on amount 0 is reachable | `web/.../relational_model/record.js` |

## Products and contacts

| Tester sees | Notes | Source |
|---|---|---|
| Product Type = Goods / Service / Combo; Sales Price; Sales Taxes; Cost; Purchase Taxes | New products get the company's default sales/purchase taxes (`account_sale_tax_id`, `account_purchase_tax_id`). Bills and RFQs take the price from Cost (RFQs only when the vendor has no price) | `product_template.py`, `account/models/product.py`, `account_move.py`, `purchase_order_line.py` |
| Tax ID | Partner field label; the company country's VAT label replaces it when set (Georgia: none) | `base/models/res_partner.py`, `base/data/res_country_data.xml` |
| Radio Person / Company above the name; field "Company" (placeholder "Company Name...") under the name, hidden on a company | Fields shown only `not is_company` / `is_company` follow the radio | `base/views/res_partner_views.xml`, `res_partner.py` `company_type` |
| Contact tabs "Contacts", "Sales & Purchase" (sections Sales, Purchase, Fiscal Information with Fiscal Position, Misc), "Invoicing" (top-level contacts only; persons of a company see "Accounting-related settings are managed on the parent company") | | `account/views/partner_view.xml` |
| Invoicing › General › "Bank accounts" = tags: type the number › `Create "…"`; tag shows "number - Bank Name" with a green shield (Trusted) or red icon (Untrusted); click it → window "Edit: …" with Account Number, Bank | Contacts › Configuration › Bank Accounts › Bank Accounts / Banks also lists them | `account/static/src/components/many2many_tags_banks`, `base/views/res_bank_views.xml`, `base/models/res_bank.py` |
| No test contact country → no fiscal position, taxes stay as proposed; a Georgian contact gets an auto-applied l10n_ge position (Georgia (VAT Registered) / Georgia (non-VAT Registered)) | Use this to get round numbers | `account/models/partner.py` `_get_fiscal_position`, `l10n_ge/data/template/account.fiscal.position-ge.csv` |
| Editable lists: [New] adds a row, [Save] / [Discard] appear while a row is edited | | `web/.../list_controller.xml` |

## Payroll

| Tester sees | Notes | Source |
|---|---|---|
| Employee tab Payroll: Contract (Start Date / End Date), Wage, **Pay Category** | The view renames Salary Structure Type to Pay Category; needs Employees Administrator | `hr/views/hr_employee_views.xml` |
| Payslip [Compute Sheet] [Validate] [Pay] [Cancel] [Set to Draft] [Revert] [Unpaid] [Create Payment Report] [Print] | Set to Draft only on Canceled; Revert and Unpaid only on Paid; Pay and Validate come from payroll accounting (without it: [Confirm], [Mark as paid]) | `hr_payroll/views/hr_payslip_views.xml`, `hr_payroll_account/views/hr_payslip_views.xml` |
| [Validate] › Are you sure you want to proceed? › [Ok] | Confirm added by payroll accounting | `hr_payroll_account/views/hr_payslip_views.xml` |
| Status Draft › Validated › Paid (Canceled) | | `hr_payslip.py` state |
| Small box Journal Entry (Draft) / Journal Entry (Posted) / Journal Entry (Canceled) | Pay refuses a non-posted entry: [Post] it first | `hr_payroll_account/views/hr_payslip_views.xml`, `hr_payroll_account/models/hr_payslip.py` |
| Tabs Worked Days, Salary Inputs, Salary Computation, Other Info | Worked Days only when the structure uses worked days | `hr_payroll/views/hr_payslip_views.xml` |
| Payslip list header [Validate] [Compute Sheet] [Confirm] [Mark as Paid] [Print]; Actions › Cancel / Set to Draft | Mark as Paid changes the status without a payment: put it in "Never" | `hr_payroll/views/hr_payslip_views.xml` (list + server actions) |
| Pay Runs › [New] › New Pay Run window: Salary Structure, Pay Schedule, Period › [Continue] › tick employees › [Select] | Opens the run's payslip list | `hr_payslip_run_views.xml`, `payslip_run_form/hr_payslip_run_form.xml`, `hr_version_list_controller.xml` |
| [Revert] on a Paid payslip › "Are you sure you want to revert this payslip? This will create a negative of this payslip." | | `hr_payroll/views/hr_payslip_views.xml` |
| Yellow bar "The employee's data has been updated since this payslip was created." › [Adjust payslip] › Payslip Correction › [Correct payslip] / [Revert only] | | `hr_payslip_views.xml`, `hr_payslip_correction_wizard_views.xml` |
| Pay window (payment wizard) [Create Payments] / [Create Payment] | Label follows the number of payments | `account/wizard/account_payment_register_views.xml` |
| User menu › My Preferences | Opens Change my Preferences (dialog, [Save]); modules add tabs there | `user_menu_items.js`, `hr/views/res_users.xml` |
| Timesheets › Timesheets › All Timesheets | Opens as a grid; list icon for the list (Date, Employee, Project, Task, Description, Time Spent) | `hr_timesheet_menus.xml`, `timesheet_grid/views/account_analytic_line_views.xml` |

## Scheduled actions

Form button [Run Manually] (`base/views/ir_cron_views.xml`). Most of our crons ship inactive; say
so in the checklist and have the tester run them by hand.

## Base rows for sheet "Where to find things"

Copy the rows that the checklist uses, then add the module's own places (its tab, status box,
tables) with the words printed on its screen:

```json
[
 ["Buttons at the top", "Top of the record, on the left, just under its name.", "[Confirm] [Reset to Draft] … (list the ones the tests use)"],
 ["Top right (status)", "Top of the record, on the right, same line as those buttons.", "The status words; the current one is highlighted."],
 ["Tab <Name>", "In the middle of the record, next to the other tabs.", "Click it."],
 ["Pop-up window", "Opens in the middle of the screen.", "An error or a question. Read it, then close it."],
 ["Small message (top right)", "Top right corner of the screen; goes away by itself.", "For example: <a real message>."],
 ["Corner ribbon", "A diagonal band in the top right corner of the page.", "<the ribbons the tests use>"],
 ["Small boxes (top right of the page)", "Top right of the page, above the fields.", "<smart button labels> — click one to open that document."],
 ["Gear icon · cloud icon · X icon", "Next to the record name at the very top.", "Gear: Duplicate, Delete. Cloud: save. X: discard your changes."],
 ["Grid icon", "Top left corner of the screen.", "Opens the list of apps."],
 ["Chatter", "Right side of the screen (or under the record).", "Messages and To-Do tasks."]
]
```
