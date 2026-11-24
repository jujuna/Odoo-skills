# Playbook: Employees, Time Off, Attendance, Payroll, Timesheets

Use this as a research starting point, not a ready-made recommendation. Historical
verification notes below do not certify the current checkout or client database. Re-check
material rules, defaults, calculations and labels before using them. Follow SKILL.md and
the implementation protocol for discovery and decisions.


Decisions to settle with the client, with what Odoo really does for each option. Verified
against Odoo 19 source (2026-10-31). Deeper detail is in `documentations/hr_holidays.md`,
`hr_holidays_accrual_plans.md`, `hr_holidays_time_off_units.md`, `work_entries.md` and
`hr_payroll.md`.

## Odoo 19 points that mislead anyone who knows older versions

- **No separate contract document.** Wage, working hours and contract dates live on dated
  versions of the employee record (**Effective Date**). Old habits of "open the contract"
  no longer apply.
- **No public holiday data ships with Odoo 19.** Georgian holidays must be entered by hand
  in **Public Holidays**.

## How Odoo thinks

| Idea | In plain words |
|---|---|
| **Time Off Type** | A kind of absence (annual, sick, unpaid). Holds the rules: approval, duration type, allocation, negative cap |
| **Allocation** | A balance given to an employee for one Time Off Type ("21 days of annual leave for 2026") |
| **Accrual Plan** | Rules that make an allocation grow over time instead of granting everything at once |
| **Time Off request** | An employee's request. States: **To Approve**, **Second Approval**, **Approved**, **Refused**, **Cancelled** |
| **Working schedule** | Decides which days and hours count as work, and so how many days a leave costs |

## Time Off decisions

**1. Does this type need a balance?** Time Off Type, block **Allocation Requests**, **Requires
allocation**.
- On: requests are refused without a valid allocation. Use for quota leave (annual).
- Off: unlimited requests, no balance tracking. Use for sick leave, unpaid leave.
- **Locked** once any leave of that type exists. The fix is to create a new type.
  (`addons/hr_holidays/models/hr_leave_type.py`, `check_allocation_requirement_edit_validity`)

**2. Grant once, or earn over time?** On the allocation: **Allocation Type** **Regular
Allocation** or **Accrual Allocation**, then an **Accrual Plan** (**Time Off > Configuration >
Accrual Plans**). Choosing a plan makes the allocation an accrual.
- Regular: all days available at once, valid until the **End Date**.
- Accrual: starts at 0, and days are added by a **daily** scheduled job. Example: 1.75
  days/month for 12 months = 21 days.

**3. Earn at the start or the end of the period?** Accrual plan, **When the time is
accrued?**: **At the start of the accrual period** / **At the end of the accrual period**
(default: end).
- Example: 2 days/month, employee starts 15 January. A partial first period is prorated
  (about 1.1 days); with "start" they are available at the beginning of the period, with
  "end" when the period closes.
- **It is based on worked time?** (only with "end"): unpaid absences reduce what is earned.

**4. What happens to unused days?** Accrual plan, **Do you need a carry-over of the accrued
days from one year to another?** and **When do you want the accrued time left to be
carried-over?** (**At the start of the year** / **At the allocation date** / **Custom
date**). Per milestone: **After a year, unused time off will be**: **Lost** / **Carried
over**, **How much time can be carried over** (**Unlimited** / **Up to**), and **Define a
carry over validity?**.
- Example: 8 days unused on 1 January, carry over "Up to 5", valid 3 months. 5 days move
  over and 3 are lost; the 5 carried days expire on 1 April if unused.
- Applies only to accrual allocations. Regular allocations just expire at their End Date.

**5. Can the balance go negative?** Time Off Type, block **Negative Cap**: **Allow Negative
Cap**, "up to" the **Maximum Excess Amount**.
- Example: 10 days allocated, excess 3. Up to 13 days can be requested, and the 14th is
  refused. The employee still needs some allocation.

**6. Who approves?** Time Off Type, **Approval** under **Time Off Requests**, and a separate
**Approval** under **Allocation Requests** (visible when **Requires allocation** is on).
Options: **None needed** / **By Time Off Officer** / **By Employee's Approver** / **By
Employee's Approver and Time Off Officer**. Default: **By Time Off Officer**.
- **None needed**: auto-approved. The two-step option: the first approval puts the request
  in **Second Approval**.
- Trap: the employee's **Time Off Approver** follows the manager's user. If the manager has
  no user, it stays empty and an administrator or officer approves. Set it deliberately.
- **Notify HR** on the type lists the officers who get notified.

**7. Smallest request.** Time Off Type, **Duration Type**: **Day** / **Half-Day** / **Hours**
(default: Day).
- Example: Half-Day lets someone take 0.5 day. Hours allows a 2-hour doctor visit.

**8. Public holidays and blocked days.** **Time Off > Configuration > Public Holidays** and
**Mandatory Days**. Time Off Type checkbox **Ignore Public Holidays**.
- Misleading label: checking **Ignore Public Holidays** *counts* holidays as leave days
  (its tooltip: "Public holidays should be counted in the leave duration when applying for
  leaves").
- A holiday added after approval gives the day back automatically and notifies the
  employee.
- On a Mandatory Day, employees can't request leave. Time Off officers still can.

**9. Overtime and undertime.** **Attendances > Configuration > Overtime Rulesets**: rules
with **Pay Extra Hours** and a **Rate**; with Time Off installed, **Give back as time off**.
A Time Off Type with **Deduct Extra Hours** lets employees spend extra hours as leave.

## Attendance and payroll decisions

**10. Pay from the schedule or from check-ins?** Employee (version) field **Work Entry
Source**: **Working Schedule** / **Attendances** (with Attendances installed) / **Planning** (with
Planning installed).
- Working Schedule: work entries come from the schedule minus leaves (salaried office staff).
- Attendances: work entries come from the employee's check-ins (hourly, shift, factory).
- Planning: work entries come from planned shifts.
- Timesheets are not a work entry source.

**11. Approve extra hours?** Attendances settings, **Extra Hours Validation**:
**Automatically Approved** / **Approved by Manager**.

**12. Leave approved after the payslip is done.** The leave gets **Payslip State** "To defer
to next payslip", and a payroll user clicks **Report to Next Month**. The activity goes to
the **Responsible** under **Deferred Time Off** in Payroll settings. A leave covered by a
validated payslip can't be deleted.

## Timesheets and billing

**13. How are hours billed?** Service product **Invoicing Policy**: **Prepaid/Fixed Price** /
**Based on Timesheets** / **Based on Milestones** (with the Milestones feature) / **Based on
Delivered Quantity (Manual)**. Timesheets settings, block **Billing**, **Invoicing Policy**,
**Invoice**: "All recorded timesheets" / "Validated timesheets only" (Enterprise).
- Example: 10 hours at 100/hour on "Based on Timesheets" = 1,000 to invoice. On Fixed
  Price, the hours are only a cost for margin reporting.

## Questions to ask the client

1. Which leave types exist, and which have a yearly quota?
2. Is annual leave given on 1 January, or earned monthly? What about new hires?
3. Carry-over: allowed? How much? Until when?
4. Who approves: manager, HR, or both? Different per type?
5. Days or hours? Half-days allowed?
6. Are working days or calendar days counted (check Georgian labour law per type)?
7. Salaried on schedule, or paid by attendance?
