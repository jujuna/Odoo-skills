-- Field or method names used by code and domains stored in the database, which no grep finds:
-- server actions and crons, automations, saved filters, window actions, record rule domains (ir_rule),
-- mail templates, export lists, custom fields, views, report print names, defaults, salary rules,
-- and accounting report formulas. Read-only.
-- Run: psql -p 5432 -d <db> -At -v name=<field_or_method> -f .claude/skills/odoo-dev/scripts/db_refs.sql
-- Output: kind|id|model|name, one line per hit; no line means no hit. A missing table (app not
-- installed) prints an error for that kind only.
\set re '\\m' :name '\\M'

SELECT 'server action or cron', a.id, m.model, a.name->>'en_US'
  FROM ir_act_server a JOIN ir_model m ON m.id = a.model_id
 WHERE concat_ws(' ', a.code, a.update_path, a.value) ~ :'re';

SELECT 'automation', b.id, m.model, b.name->>'en_US'
  FROM base_automation b JOIN ir_model m ON m.id = b.model_id
 WHERE concat_ws(' ', b.filter_domain, b.filter_pre_domain) ~ :'re';

SELECT 'saved filter', f.id, f.model_id, f.name
  FROM ir_filters f
 WHERE concat_ws(' ', f.domain, f.context) ~ :'re';

SELECT 'window action', w.id, w.res_model, w.name->>'en_US'
  FROM ir_act_window w
 WHERE concat_ws(' ', w.domain, w.context) ~ :'re';

SELECT 'record rule', r.id, m.model, r.name
  FROM ir_rule r JOIN ir_model m ON m.id = r.model_id
 WHERE r.domain_force ~ :'re';

SELECT 'mail template', t.id, t.model, t.name->>'en_US'
  FROM mail_template t
 WHERE concat_ws(' ', t.subject::text, t.email_to, t.email_from, t.body_html::text) ~ :'re';

SELECT 'export list', e.id, x.resource, concat_ws(' / ', x.name, e.name)
  FROM ir_exports_line e LEFT JOIN ir_exports x ON x.id = e.export_id
 WHERE e.name ~ :'re';

SELECT 'custom field', c.id, c.model, c.name
  FROM ir_model_fields c
 WHERE c.state = 'manual' AND concat_ws(' ', c.related, c.depends, c.compute, c.domain) ~ :'re';

SELECT 'view without module file', v.id, v.model, v.name
  FROM ir_ui_view v
 WHERE v.active AND v.arch_db::text ~ :'re'
   AND NOT EXISTS (SELECT 1 FROM ir_model_data d
                    WHERE d.model = 'ir.ui.view' AND d.res_id = v.id
                      AND d.module NOT IN ('__export__', 'studio_customization'));

SELECT 'report print name', r.id, r.model, r.name->>'en_US'
  FROM ir_act_report_xml r
 WHERE r.print_report_name ~ :'re';

SELECT 'user default', d.id, f.model, f.name
  FROM ir_default d JOIN ir_model_fields f ON f.id = d.field_id
 WHERE concat_ws(' ', f.name, d.condition) ~ :'re';

SELECT 'salary rule', s.id, 'hr.salary.rule', s.code
  FROM hr_salary_rule s
 WHERE concat_ws(' ', s.condition_python, s.amount_python_compute) ~ :'re';

SELECT 'account report expression', e.id, 'account.report.expression', e.label
  FROM account_report_expression e
 WHERE concat_ws(' ', e.formula, e.subformula) ~ :'re';
