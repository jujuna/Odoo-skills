"""Assemble a module's developer_map.html from map_gen.py's data and a hand-written parts file.

The hand file (see rs_einvoice_hand.py) holds PURPOSES, LENSES, SCENARIOS, COLUMNS, CONTROLS, MODELS and
QUESTIONS plus a sid() resolver; the meta block below is still specific to rs_einvoice and is edited
per module. The shell (CSS and JS) is taken from an existing developer_map.html, e.g. geo_payroll's."""
import json
import sys
from pathlib import Path

import importlib.util
import re

if len(sys.argv) != 5:
    sys.exit('usage: map_build.py <module_dir> <auto.json from map_gen.py> <hand.py> <shell developer_map.html>')
MOD = Path(sys.argv[1]).resolve()
auto = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
_spec = importlib.util.spec_from_file_location('map_hand', sys.argv[3])
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)
_shell = Path(sys.argv[4]).read_text(encoding='utf-8')
_pre, _rest = _shell.split('<script id="data" type="application/json">', 1)
_post = _rest.split('</script>', 1)[1]
symbols = auto['symbols']
edges = auto['edges']
by_id = {s['id']: s for s in symbols}
problems = []

# purposes
for key, text in H.PURPOSES.items():
    full = H.sid(key)
    if full not in by_id:
        problems.append('purpose for unknown symbol %s' % full)
        continue
    if by_id[full]['purpose']:
        problems.append('purpose given but docstring exists: %s' % full)
    by_id[full]['purpose'] = text
missing = [s['id'] for s in symbols if not s['purpose']]
if missing:
    problems.append('symbols still without purpose: %s' % missing)

# lenses
lenses = []
covered = set()
for spec in H.LENSES:
    nodes, lanes, row = [], [], 0
    for label, model, rows in spec['lanes']:
        first = row
        for r in rows:
            for c, item in enumerate(r):
                if item is None:
                    continue
                key, cap = (item, None) if isinstance(item, str) else item
                full = H.sid(key)
                if full not in by_id:
                    problems.append('lens %s: unknown %s' % (spec['key'], full))
                    continue
                if any(n['id'] == full for n in nodes):
                    problems.append('lens %s: duplicate %s' % (spec['key'], full))
                node = {'id': full, 'col': c, 'row': row}
                if cap:
                    node['cap'] = cap
                nodes.append(node)
                covered.add(full)
            row += 1
        lanes.append({'model': model, 'label': label if label != model else '', 'rows': [first, row - 1]})
    lenses.append({'key': spec['key'], 'title': spec['title'], 'blurb': spec['blurb'], 'lanes': lanes, 'nodes': nodes})

uncovered = [s['id'] for s in symbols if s['id'] not in covered]
if uncovered:
    nodes = []
    per_row = 5
    for i, full in enumerate(uncovered):
        nodes.append({'id': full, 'col': i % per_row, 'row': i // per_row})
    rows = (len(uncovered) + per_row - 1) // per_row
    lenses.append({'key': 'rest', 'title': 'Other helpers', 'blurb': 'Helpers, computes and thin wrappers that no flow lens shows; click one to see its callers and what it uses.', 'lanes': [{'model': '', 'label': 'helpers', 'rows': [0, rows - 1]}], 'nodes': nodes})

# scenarios
for sc in H.SCENARIOS:
    for st in sc['steps']:
        if st['node'] not in by_id:
            problems.append('scenario %s: unknown node %s' % (sc['key'], st['node']))
    if sc['lens'] not in {l['key'] for l in lenses}:
        problems.append('scenario %s: unknown lens %s' % (sc['key'], sc['lens']))

# columns, controls, models, questions
for c in H.COLUMNS + H.CONTROLS:
    for m in c['methods']:
        if m not in by_id:
            problems.append('column %s: unknown %s' % (c['field'], m))
for n in H.MODELS['nodes']:
    for m in n['methods']:
        if m not in by_id:
            problems.append('model %s: unknown %s' % (n['id'], m))
model_ids = {n['id'] for n in H.MODELS['nodes']}
for e in H.MODELS['edges']:
    if e['from'] not in model_ids or e['to'] not in model_ids:
        problems.append('model edge with unknown node: %s -> %s' % (e['from'], e['to']))
scen_keys = {sc['key'] for sc in H.SCENARIOS}
for qq in H.QUESTIONS:
    for m in qq['methods']:
        if m not in by_id:
            problems.append('question: unknown %s' % m)
    if qq.get('run') and qq['run'] not in scen_keys:
        problems.append('question: unknown run %s' % qq['run'])

if problems:
    print('\n'.join(problems))
    sys.exit(1)

# meta
reached = sum(1 for s in symbols if any(t['kind'] != 'direct_only' for t in s['triggers']))
orm_edges = sum(1 for e in edges if e['kind'] == 'orm_dispatch')
meta = {
    'title': 'RS E-Invoice Wiring',
    'module': 'rs_einvoice',
    'version': '20.0.1.0.0',
    'odoo': '20',
    'columns_label': 'rs.ge calls',
    'controls_label': 'Kept in Odoo, never sent to rs.ge',
    'about': 'A static reading of the working tree of `rs_einvoice` 19.0.1.0.0 on <date> (module repository commit <hash>). Every method and function of the models and wizards is a box; every arrow is a call site found in the source, a property read, or a constraint the ORM fires on create and write. Nothing was executed: no Odoo, no tests, no rs.ge.',
    'limits': [
        'The method records (purpose, how, reads, changes, the catch, traps) were generated by a script from the source: the docstring, the statements in order, the raises, the commits, the field reads and writes. The methods without a docstring got a purpose written by hand from their code. No record was re-read by a second reader; the source is under each box and is the reference.',
        'Call edges are resolved by name: `self.x()` to the method of the same model, `receiver.x()` to the unique method of that name or, when several models define it, to the account.move one. A call through a variable holding another model, or through `getattr`, is not drawn. Constraints are drawn as dashed reaches from `create` and `write`; computes and onchanges are entry points without wires.',
        'Behaviour of core Odoo 19 (`action_post`, `_reverse_moves`, `copy`, the reversal wizard, locks, savepoints) and of rs_base_methods (the login fields, Test SOAP, `_rs_responsible_user`) is read where a wire depends on it but not drawn; those calls appear as dotted chips.',
        'The seven scenarios use the values of the module tests (tests/test_seller_flow.py, test_buyer_inbox.py, test_write_guards.py) where a test exists, and values derived from the source elsewhere (the cancellation in an earlier period, the correction chain, the per-company cron). Amounts follow the rules in the source; none was produced by running Odoo.',
        'The rs.ge calls page lists the SOAP operations the service invokes and what the module reads from the replies, as far as the recorded replies in tests/stub_responses.py and the parsing code show; rs.ge fields the module never reads are not listed.',
        'Wire line numbers are resolved from the source when the page is built, so they match the snapshot listed on this page; a later edit moves them.',
    ],
    'reading': [
        'Map: pick a lens, click a box. Amber = who calls it, teal = what it uses, dashed = the ORM reaches it (a constraint on create or write), the left stripe colour = how Odoo reaches it (button, cron, compute, constraint, onchange, core override).',
        'Run a scenario: the box that is executing pulses; the values panel shows what exists at that moment; changed values are blue.',
        'rs.ge calls: one card per SOAP operation: who calls it, what rs.ge answers and how it is read, what the user sees when it fails; the last row shows the records the module keeps that never reach rs.ge.',
        'Models: arrows point from the field to the record it references; click a model for its decision fields and guards.',
        'Search with `/`, step with the arrow keys, clear with Esc. The URL hash keeps your position, so links into the map work.',
    ],
    'files': auto['files'],
    'facts': {
        'analysed': '2026-09-29',
        'built from commit': '3c8faf2b198809e109799ddd36addcd18655f28a, plus the uncommitted working tree of 2026-09-29',
        'module version': '20.0.1.0.0',
        'methods, getters, functions': str(len(symbols)),
        'reached by Odoo or the browser': '%d (button, cron, constraint, compute, onchange, core override)' % reached,
        'relationships': '%d (%d through the ORM, %d property reads)' % (len(edges), orm_edges, sum(1 for e in edges if e['kind'] == 'getter_read')),
        'lenses': str(len(lenses)),
        'scenarios': str(len(H.SCENARIOS)),
        'method records': '%d generated from the source by script; %d purposes written by hand for methods without a docstring; not independently re-read' % (len(symbols), len(H.PURPOSES)),
        'scope': 'models, wizards, views (buttons), data (crons), security; tests read for the scenario values; no JS, no SCSS, no i18n',
    },
}

data = {
    'meta': meta,
    'symbols': symbols,
    'edges': edges,
    'lenses': lenses,
    'scenarios': H.SCENARIOS,
    'columns_intro': {'title': 'The rs.ge calls', 'lead': 'The module talks to rs.ge through `rs.soap.service`, one method per SOAP operation. Pick an operation to see who calls it, what rs.ge answers and how the module reads it, and what the user sees when it fails. The last row lists the records the module keeps in Odoo that never reach rs.ge.'},
    'columns': H.COLUMNS,
    'controls': H.CONTROLS,
    'models': H.MODELS,
    'questions_intro': {'title': 'Questions a developer asks in the first hour', 'lead': 'Short answers with the methods to open. Each answer is checked against the source of 2026-09-29.'},
    'questions': H.QUESTIONS,
}

pre = re.sub(r'<title>.*?</title>', '<title>%s</title>' % meta['title'], _pre, count=1)
post = _post
payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
html = pre + '<script id="data" type="application/json">' + payload + '</script>' + post
out = MOD / 'developer_map.html'
out.write_text(html, encoding='utf-8')
print('written', out, len(html), 'chars;', len(symbols), 'symbols,', len(edges), 'edges,', len(lenses), 'lenses,', len(uncovered), 'in the helpers lens')
