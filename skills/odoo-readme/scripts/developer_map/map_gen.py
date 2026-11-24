"""Generate the symbols, edges and file facts of a module's developer map from its source.

Usage: python3 map_gen.py <module_dir> <out.json>; then map_build.py assembles the page.

Every record is derived from the AST: docstrings, call sites, raises, commits, field reads
and writes, decorators, view buttons and cron entries. Nothing is executed.
"""
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

if len(sys.argv) != 3:
    sys.exit('usage: map_gen.py <module_dir> <out.json>')
MOD = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])

PY_FILES = sorted(list((MOD / 'models').glob('*.py')) + list((MOD / 'wizard').glob('*.py')))
PY_FILES = [p for p in PY_FILES if p.name != '__init__.py']

CORE_OVERRIDES = {
    'create', 'write', 'unlink', 'init', '_post', 'button_draft', 'button_cancel', 'default_get',
    '_prepare_default_reversal', 'refund_moves', 'modify_moves', '_compute_display_name',
    '_compute_show_reset_to_draft_button', '_compute_show_refresh_out_einvoices_status_button',
    'button_refresh_out_einvoices_status',
}
CORE_FIELDS = {
    'state', 'move_type', 'partner_id', 'company_id', 'invoice_date', 'date', 'currency_id',
    'reversed_entry_id', 'reversal_move_ids', 'payment_state', 'invoice_line_ids', 'line_ids',
    'name', 'display_name', 'journal_id', 'amount_total', 'amount_untaxed', 'amount_tax', 'vat',
    'ref', 'invoice_origin', 'is_downpayment', 'price_total', 'price_subtotal', 'price_unit',
    'quantity', 'tax_ids', 'product_id', 'product_uom_id', 'display_type', 'sale_line_ids',
    'purchase_line_id', 'account_id', 'move_ids', 'new_move_ids', 'active_ids', 'user_id',
    'rs_username', 'rs_un_id', 'rs_user_id', 'lock_date', 'fiscalyear_lock_date', 'tax_lock_date',
    'sale_lock_date', 'purchase_lock_date', 'commercial_partner_id', 'root_id', 'type', 'sequence',
}
SERVICE_RECEIVERS = {'service', 'svc', 'rs', 'soap'}
CORE_CALLS = {
    'action_post': 'core account.move.action_post', 'button_cancel': 'core account.move.button_cancel',
    'button_draft': 'core account.move.button_draft', '_reverse_moves': 'core account.move._reverse_moves',
    'copy': 'core copy()', 'message_post': 'mail.thread.message_post', 'activity_schedule': 'mail.activity.schedule',
    'lock_for_update': 'core lock_for_update (FOR UPDATE NOWAIT)', 'try_lock_for_update': 'core try_lock_for_update (SKIP LOCKED)',
    '_commit_progress': 'ir.cron._commit_progress', 'invalidate_all': 'env.invalidate_all',
    'invalidate_recordset': 'invalidate_recordset', 'savepoint': 'cr.savepoint', 'flush_all': 'env.flush_all',
    'get_version': 'core', '_get_version': 'core', 'search': None, 'create': None, 'write': None, 'browse': None,
}


def relpath(p):
    return str(p.relative_to(MOD))


def first_sentence(doc):
    doc = ' '.join(doc.strip().split())
    if not doc:
        return ''
    m = re.match(r'(.+?[.!?])(\s|$)', doc)
    return (m.group(1) if m else doc)[:260]


def rest_sentences(doc):
    doc = ' '.join(doc.strip().split())
    first = first_sentence(doc)
    rest = doc[len(first):].strip()
    parts = [s.strip() for s in re.split(r'(?<=[.!?])\s+', rest) if s.strip()]
    return parts


def dec_text(d):
    try:
        t = ast.unparse(d)
    except Exception:
        return '?'
    t = t.replace("'", '')
    return t if len(t) <= 48 else t[:45] + '...'


def raise_message(node):
    """The start of the user-facing text of a raise, when the exception is built from a literal."""
    exc = node.exc
    if not isinstance(exc, ast.Call):
        return None
    fname = ast.unparse(exc.func)
    if not exc.args:
        return fname
    a = exc.args[0]
    text = None
    if isinstance(a, ast.Call) and isinstance(a.args[:1], list) and a.args and isinstance(a.args[0], ast.Constant):
        text = a.args[0].value
    elif isinstance(a, ast.Constant):
        text = a.value
    elif isinstance(a, ast.BinOp) and isinstance(a.left, ast.Call) and a.left.args and isinstance(a.left.args[0], ast.Constant):
        text = a.left.args[0].value
    if isinstance(text, str):
        text = ' '.join(text.split())
        return (fname.split('.')[-1] + ': "' + (text[:90] + ('…' if len(text) > 90 else '')) + '"')
    return fname.split('.')[-1]


class Collector:
    def __init__(self):
        self.symbols = []
        self.by_owner_name = {}
        self.by_name = {}
        self.fields = {}      # owner -> {field: (type, compute)}
        self.compute_sql = {}  # method name -> field
        self.properties = {}
        self.files = []
        self.raw = []         # (symbol, funcnode, owner, file, source_lines)

    def add_file(self, path):
        src = path.read_text(encoding='utf-8')
        lines = src.splitlines()
        tree = ast.parse(src)
        rel = relpath(path)
        self.files.append({'path': rel, 'sha': hashlib.sha1(src.encode()).hexdigest()[:12], 'lines': len(lines)})
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self._add_func(node, rel, owner=path.stem, cls=None, lines=lines)
            elif isinstance(node, ast.ClassDef):
                owner = None
                for st in node.body:
                    if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                        if st.targets[0].id == '_name' and isinstance(st.value, ast.Constant):
                            owner = st.value.value
                        elif st.targets[0].id == '_inherit' and owner is None:
                            if isinstance(st.value, ast.Constant):
                                owner = st.value.value
                            elif isinstance(st.value, (ast.List, ast.Tuple)) and st.value.elts:
                                owner = st.value.elts[0].value
                owner = owner or node.name
                # fields
                for st in node.body:
                    if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name) \
                            and isinstance(st.value, ast.Call) and ast.unparse(st.value.func).startswith('fields.'):
                        ftype = ast.unparse(st.value.func).split('.')[-1]
                        compute = None
                        for kw in st.value.keywords:
                            if kw.arg == 'compute' and isinstance(kw.value, ast.Constant):
                                compute = kw.value.value
                            if kw.arg == 'compute_sql' and isinstance(kw.value, ast.Constant):
                                self.compute_sql[kw.value.value] = st.targets[0].id
                        self.fields.setdefault(owner, {})[st.targets[0].id] = (ftype, compute)
                for st in node.body:
                    if isinstance(st, ast.FunctionDef):
                        self._add_func(st, rel, owner=owner, cls=node.name, lines=lines)

    def _add_func(self, fn, rel, owner, cls, lines):
        start = min([d.lineno for d in fn.decorator_list] + [fn.lineno])
        end = fn.end_lineno
        sid = f"{rel}::{cls}.{fn.name}" if cls else f"{rel}::{fn.name}"
        doc = ast.get_docstring(fn) or ''
        sym = {
            'id': sid, 'name': fn.name, 'owner': owner, 'kind': 'python', 'file': rel,
            'def_line': fn.lineno, 'start_line': start, 'end_line': end,
            'decorators': [dec_text(d) for d in fn.decorator_list],
            'code': '\n'.join(lines[start - 1:end]),
            'build': False, 'purpose': first_sentence(doc), 'how': [], 'reads': [], 'changes': [],
            'catch': '', 'triggers': [], 'traps': [], 'external': [],
            '_doc_rest': rest_sentences(doc), '_module_function': cls is None,
        }
        self.symbols.append(sym)
        self.by_owner_name[(owner, fn.name)] = sym
        self.by_name.setdefault(fn.name, []).append(sym)
        self.raw.append((sym, fn, owner))

    # ---------------------------------------------------------------- analysis
    def resolve(self, owner, name, receiver):
        """The module symbol a call `receiver.name(` most plausibly reaches."""
        cands = self.by_name.get(name) or []
        if not cands:
            return None
        if receiver in ('self', 'super()') or receiver is None:
            same = self.by_owner_name.get((owner, name))
            return same
        same = self.by_owner_name.get((owner, name))
        if len(cands) == 1:
            return cands[0]
        if same:
            return same
        # ambiguous across owners: prefer account.move (the bulk of the module)
        for c in cands:
            if c['owner'] == 'account.move':
                return c
        return None

    def analyse(self):
        edges = []
        self.properties = {s['name']: s for s in self.symbols if any(d == 'property' for d in s['decorators'])}
        for sym, fn, owner in self.raw:
            how, reads, changes, external, traps = [], [], [], [], []
            n_raise = 0
            service_ops = []
            commits = 0
            sudo = False
            broad_except = False
            raw_sql = False
            ctx_bypass = set()
            written = set()
            read_attrs = set()
            seen_calls = set()
            for node in ast.walk(fn):
                # a @property of the model read as an attribute
                if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and node.attr in self.properties:
                    target = self.by_owner_name.get((owner, node.attr)) or self.properties[node.attr]
                    if target and target['id'] != sym['id'] and target['id'] not in seen_calls:
                        seen_calls.add(target['id'])
                        edges.append({'from': sym['id'], 'to': target['id'], 'line': node.lineno, 'kind': 'getter_read'})
                # reads
                if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                    known = set(self.fields.get(owner, {})) | CORE_FIELDS
                    if node.attr in known and not (isinstance(node.value, ast.Name) and node.value.id in ('vals', 'fields', 'result')):
                        read_attrs.add(node.attr)
                # writes: attribute assignment
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Attribute):
                            written.add(t.attr)
                if isinstance(node, ast.Call):
                    f = node.func
                    fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
                    recv = None
                    if isinstance(f, ast.Attribute):
                        try:
                            recv = ast.unparse(f.value)
                        except Exception:
                            recv = None
                    if fname == 'write' and isinstance(f, ast.Attribute) and node.args and isinstance(node.args[0], ast.Dict):
                        for k in node.args[0].keys:
                            if isinstance(k, ast.Constant):
                                written.add(k.value)
                    if fname == 'commit' and recv and recv.endswith('cr'):
                        commits += 1
                    if fname == 'sudo':
                        sudo = True
                    if fname == 'execute' and recv and recv.endswith('cr'):
                        raw_sql = True
                    if fname == 'with_context':
                        for kw in node.keywords:
                            if kw.arg and kw.arg.startswith('rs_'):
                                ctx_bypass.add(kw.arg)
                    # service calls
                    if recv and (recv in SERVICE_RECEIVERS or recv.endswith('.service') or recv.startswith('client.service')):
                        if fname and fname not in ('with_company', 'with_user', 'sudo', 'with_context'):
                            if recv.startswith('client.service'):
                                service_ops.append('rs.ge SOAP `%s`' % fname)
                            elif self.by_owner_name.get(('rs.soap.service', fname)) and owner != 'rs.soap.service':
                                pass  # a module call, handled below
                            else:
                                service_ops.append('rs.ge `%s`' % fname)
                    # module calls
                    if fname:
                        target = None
                        if recv and (recv in SERVICE_RECEIVERS or recv.endswith('.service')) and self.by_owner_name.get(('rs.soap.service', fname)):
                            target = self.by_owner_name[('rs.soap.service', fname)]
                        elif recv and recv.startswith("self.env['") and "']" in recv:
                            model = recv.split("'")[1]
                            target = self.by_owner_name.get((model, fname))
                        elif recv and (recv == 'self' or recv.startswith('self.') or recv.startswith('super')) and recv.count('.') <= 1:
                            target = self.resolve(owner, fname, 'self')
                        elif recv and re.match(r'^[a-z_]+(\.[a-z_]+)?$', recv or ''):
                            target = self.resolve(owner, fname, recv)
                        elif recv is None and isinstance(f, ast.Name):
                            # a bare call to a module-level helper of this or another file
                            cands = [s for s in self.by_name.get(fname, []) if '.' not in s['id'].split('::')[1]]
                            target = cands[0] if len(cands) == 1 else None
                        if recv and recv.startswith('super'):
                            target = None
                            external.append('`super().%s` (core, outside this module)' % fname)
                        if target and target['id'] != sym['id']:
                            key = target['id']
                            if key not in seen_calls:
                                seen_calls.add(key)
                                edges.append({'from': sym['id'], 'to': target['id'], 'line': node.lineno, 'kind': 'call'})
                        elif not target and fname in CORE_CALLS and CORE_CALLS[fname] and recv and not recv.startswith('super'):
                            ext = '`%s` (%s)' % (fname, CORE_CALLS[fname])
                            if ext not in external:
                                external.append(ext)
                if isinstance(node, ast.Raise):
                    n_raise += 1
                if isinstance(node, ast.ExceptHandler):
                    t = node.type
                    if t is None or (isinstance(t, ast.Name) and t.id == 'Exception'):
                        broad_except = True
            # ordered "how": walk statements in order, top level of the function body + nested blocks
            steps = []

            def emit(text):
                if len(steps) < 16 and (not steps or steps[-1] != text):
                    steps.append(text)

            for node in ast.walk(fn):
                pass
            for stmt in self._ordered_statements(fn):
                if isinstance(stmt, ast.Raise):
                    m = raise_message(stmt)
                    if m:
                        emit('refuse — ' + m)
                elif isinstance(stmt, (ast.Expr, ast.Assign, ast.AugAssign, ast.Return, ast.AnnAssign)):
                    for node in ast.walk(stmt):
                        if isinstance(node, ast.Call):
                            f = node.func
                            fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
                            recv = ast.unparse(f.value) if isinstance(f, ast.Attribute) else None
                            if fname == 'commit' and recv and recv.endswith('cr'):
                                emit('`cr.commit()` — the work so far is durable')
                            elif recv and recv.startswith('super'):
                                emit('`super().%s()`' % fname)
                            elif recv and (recv in SERVICE_RECEIVERS or recv.endswith('.service')) and fname:
                                if self.by_owner_name.get(('rs.soap.service', fname)):
                                    emit('rs.ge call `%s`' % fname)
                                elif recv.startswith('client.service'):
                                    emit('SOAP operation `%s`' % fname)
                            elif fname and recv and (recv == 'self' or recv in ('move', 'locked', 'original', 'parent', 'partner', 'new_invoice', 'target', 'bill', 'invoice')):
                                t = self.resolve(owner, fname, recv if recv != 'self' else 'self')
                                if t and t['id'] != sym['id']:
                                    emit('`%s`' % fname)
                            elif fname == 'write' and recv and node.args and isinstance(node.args[0], ast.Dict):
                                keys = [k.value for k in node.args[0].keys if isinstance(k, ast.Constant)]
                                if keys:
                                    emit('write %s' % ', '.join('`%s`' % k for k in keys[:5]))
                    if isinstance(stmt, ast.Assign):
                        for t in stmt.targets:
                            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in ('self', 'move', 'locked', 'original', 'parent', 'new_invoice', 'target'):
                                emit('set `%s`' % t.attr)
                    if isinstance(stmt, ast.Return) and stmt.value is not None:
                        emit('return')
            how = steps
            if not how:
                how = sym['_doc_rest'][:4] or ['Reads its inputs and returns; see the source below.']
            elif sym['_doc_rest']:
                how = sym['_doc_rest'][:3] + how
            reads = sorted(a for a in read_attrs if a not in written)
            ch = []
            for w in sorted(written):
                ch.append('sets `%s`' % w)
            if commits:
                ch.append('commits the transaction (%d×)' % commits)
            if n_raise:
                ch.append('raises in %d case%s' % (n_raise, '' if n_raise == 1 else 's'))
            has_return = any(isinstance(n, ast.Return) and n.value is not None for n in ast.walk(fn))
            if has_return:
                ch.append('returns a value')
            if not ch:
                ch.append('nothing stored: reads only')
            changes = ch
            ext = list(dict.fromkeys(service_ops + external))
            catch = ''
            if commits:
                catch = 'Commits inside the method. The pending marker / status is durable before rs.ge answers, and the row is re-locked after the commit (`_rs_relock_after_commit`); a caller must be commit-aware.'
                traps.append('`cr.commit()` here: the tests patch commit to flush; a caller inside a savepoint cannot roll this back.')
            if ctx_bypass:
                catch = catch or ('Uses the context key%s %s to pass the write guards on purpose.' % ('s' if len(ctx_bypass) > 1 else '', ', '.join('`%s`' % k for k in sorted(ctx_bypass))))
            if sudo:
                traps.append('`sudo()` inside: that step ignores access rights and record rules.')
            if broad_except:
                traps.append('A bare `except Exception` swallows the failure of that step: it is logged or written to RS Logs, never raised.')
            if raw_sql:
                traps.append('Raw SQL: the ORM cache is not aware of what it reads or writes.')
            sym.update({'how': how, 'reads': reads, 'changes': changes, 'catch': catch, 'traps': traps, 'external': ext})
        self.edges = edges

    @staticmethod
    def _ordered_statements(fn):
        out = []

        def walk(body):
            for st in body:
                out.append(st)
                for attr in ('body', 'orelse', 'finalbody', 'handlers'):
                    sub = getattr(st, attr, None)
                    if isinstance(sub, list):
                        for s in sub:
                            if isinstance(s, ast.ExceptHandler):
                                walk(s.body)
                            elif isinstance(s, ast.stmt):
                                walk([s])
        walk(fn.body)
        return out

    def triggers(self):
        # buttons from views
        buttons = {}
        for xml in sorted((MOD / 'views').glob('*.xml')):
            text = xml.read_text(encoding='utf-8')
            for m in re.finditer(r'<button[^>]*name="([a-z_0-9]+)"[^>]*>', text, re.S):
                line = text[:m.start()].count('\n') + 1
                label = re.search(r'string="([^"]+)"', m.group(0))
                buttons.setdefault(m.group(1), []).append((relpath(xml), line, label.group(1) if label else m.group(1)))
        crons = {}
        cron_xml = MOD / 'data' / 'ir_cron.xml'
        text = cron_xml.read_text(encoding='utf-8')
        for rec in re.finditer(r'<record[^>]*model="ir.cron"[^>]*>(.*?)</record>', text, re.S):
            body = rec.group(1)
            name = re.search(r'<field name="name">([^<]+)</field>', body)
            code = re.search(r'<field name="code">model\.([a-z_0-9]+)\(', body)
            every = re.search(r'<field name="interval_number">(\d+)</field>.*?<field name="interval_type">(\w+)</field>', body, re.S)
            active = re.search(r'<field name="active"[^>]*>(\w+)</field>', body)
            if code:
                crons[code.group(1)] = (name.group(1) if name else code.group(1),
                                        ('every %s %s' % every.groups()) if every else '',
                                        (active.group(1) if active else 'True'))
        callers = {}
        for e in self.edges:
            callers.setdefault(e['to'], []).append(e['from'])
        for sym in self.symbols:
            trig = []
            name = sym['name']
            if name in buttons:
                for f, line, label in buttons[name]:
                    trig.append({'kind': 'button', 'detail': 'button "%s"' % label, 'evidence': '%s:%d' % (f, line)})
            if name in crons:
                cname, every, active = crons[name]
                trig.append({'kind': 'cron', 'detail': 'scheduled action "%s", %s, %s at install' % (cname, every, 'active' if active == 'True' else 'inactive'), 'evidence': 'data/ir_cron.xml'})
            for d in sym['decorators']:
                if d.startswith('api.constrains'):
                    trig.append({'kind': 'constraint', 'detail': 'runs on create/write of %s' % d[len('api.constrains('):-1], 'evidence': sym['file'] + ':%d' % sym['def_line']})
                elif d.startswith('api.onchange'):
                    trig.append({'kind': 'onchange', 'detail': 'form onchange of %s' % d[len('api.onchange('):-1], 'evidence': sym['file'] + ':%d' % sym['def_line']})
            computed = [f for f, (t, c) in self.fields.get(sym['owner'], {}).items() if c == name]
            if computed:
                trig.append({'kind': 'compute', 'detail': 'compute of %s' % ', '.join('`%s`' % f for f in computed), 'evidence': sym['file'] + ':%d' % sym['def_line']})
            if name in self.compute_sql:
                trig.append({'kind': 'compute', 'detail': 'compute_sql of `%s`: the SQL the ORM uses to search and group on the field' % self.compute_sql[name], 'evidence': sym['file'] + ':%d' % sym['def_line']})
            if name in CORE_OVERRIDES and any('super()' in l for l in sym['code'].splitlines()):
                trig.append({'kind': 'orm_override', 'detail': 'overrides core `%s` on %s and calls super()' % (name, sym['owner']), 'evidence': sym['file'] + ':%d' % sym['def_line']})
            elif name in CORE_OVERRIDES:
                trig.append({'kind': 'orm_override', 'detail': 'replaces core `%s` on %s (no super())' % (name, sym['owner']), 'evidence': sym['file'] + ':%d' % sym['def_line']})
            if name == 'action_confirm' and sym['owner'].endswith('wizard') or (name == 'action_confirm'):
                pass
            c = callers.get(sym['id'], [])
            if c:
                trig.append({'kind': 'direct_only', 'detail': 'called from %d method%s of this module' % (len(set(c)), '' if len(set(c)) == 1 else 's'), 'evidence': ', '.join(sorted({x.split('::')[0] for x in c}))})
            elif not trig:
                trig.append({'kind': 'direct_only', 'detail': 'no caller found in this module (public API, template, or reached by name from a view/context)', 'evidence': ''})
            sym['triggers'] = trig

    def orm_edges(self):
        """Constraints fire on create/write of their model: dashed reaches from the overrides."""
        extra = []
        for sym in self.symbols:
            if any(d.startswith('api.constrains') for d in sym['decorators']):
                for src_name in ('create', 'write'):
                    src = self.by_owner_name.get((sym['owner'], src_name))
                    if src:
                        extra.append({'from': src['id'], 'to': sym['id'], 'line': src['def_line'], 'kind': 'orm_dispatch', 'label': 'constraint on %s' % src_name})
        self.edges.extend(extra)

    def finish(self):
        for s in self.symbols:
            s.pop('_doc_rest', None)
            s.pop('_module_function', None)


c = Collector()
for p in PY_FILES:
    c.add_file(p)
c.analyse()
c.orm_edges()
c.triggers()
c.finish()
manifest = (MOD / '__manifest__.py').read_text(encoding='utf-8')
for extra in ['__manifest__.py', 'data/ir_cron.xml', 'security/ir.model.access.csv'] + [relpath(p) for p in sorted((MOD / 'views').glob('*.xml'))]:
    src = (MOD / extra).read_text(encoding='utf-8')
    c.files.append({'path': extra, 'sha': hashlib.sha1(src.encode()).hexdigest()[:12], 'lines': src.count('\n') + 1})
out = {'symbols': c.symbols, 'edges': c.edges, 'files': c.files, 'fields': {k: {f: v[0] for f, v in d.items()} for k, d in c.fields.items()}}
OUT.write_text(json.dumps(out, ensure_ascii=False))
print('symbols', len(c.symbols), 'edges', len(c.edges), 'files', len(c.files))
print('no docstring:', sum(1 for s in c.symbols if not s['purpose']))
