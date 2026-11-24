#!/usr/bin/env python3
"""Print a developer's map of an Odoo 19 module, or check a README against the code.

Usage (from the project root, any Python 3.10+, no Odoo needed):
    python3 .claude/skills/odoo-readme/scripts/code_map.py MODULE_DIR
    python3 .claude/skills/odoo-readme/scripts/code_map.py MODULE_DIR --check README_DEV.md

Map mode prints Markdown: manifest facts (including hooks), per Python file its classes
(_name, _inherit), fields (relational comodel vs label handled accurately), constraints,
sudo() usage, methods with decorators/super(), data/view XML, security (ir.model.access.csv
+ ir.rule), and tests.

Check mode reads a README and verifies every `backticked` code-like name against the module
first (word-bounded) and then in one batched pass across active Odoo 19 roots (excluding
sibling duplicate copies of the same module name under other custom_addons/ project folders).
"""
import ast
import csv
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
SKIP_DIRS = {'__pycache__', 'static', 'i18n', '.git', 'migrations', 'node_modules'}
RELATIONAL_FIELDS = {'Many2one', 'One2many', 'Many2many', 'Reference'}
TOKEN_RE = re.compile(rb'[A-Za-z_][A-Za-z0-9_]*')


def active_outside_roots(module):
    candidates = [
        os.path.join(ROOT, 'odoo'),
        os.path.join(ROOT, 'addons'),
        os.path.join(ROOT, 'enterprise'),
        os.path.join(ROOT, 'custom_addons', 'gec_odoo_modules'),
        os.path.join(ROOT, 'custom_addons', 'alta_hr_customization'),
    ]
    parent_root = os.path.dirname(os.path.abspath(module))
    if os.path.isdir(parent_root) and parent_root not in candidates and parent_root != ROOT:
        candidates.append(parent_root)
    return [d for d in candidates if os.path.isdir(d)]


def rel(path, base):
    return os.path.relpath(path, base)


def py_files(module):
    for dirpath, dirnames, filenames in os.walk(module):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith('.py') and name not in ('__init__.py', '__manifest__.py'):
                yield os.path.join(dirpath, name)


def const(node):
    """Literal value of an AST node, or None."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def decorator_name(dec):
    target = dec.func if isinstance(dec, ast.Call) else dec
    name = ast.unparse(target)
    if isinstance(dec, ast.Call) and dec.args:
        first = const(dec.args[0])
        if isinstance(first, str):
            name += f"('{first}'{', ...' if len(dec.args) > 1 else ''})"
    return name


def calls_super(func):
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'super'
               for n in ast.walk(func))


def count_sudo(node):
    return sum(1 for n in ast.walk(node)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'sudo')


def first_doc_line(node):
    doc = ast.get_docstring(node)
    return doc.strip().splitlines()[0] if doc else ''


def field_line(target, call):
    ftype = ast.unparse(call.func).replace('fields.', '')
    comodel = None
    label = None
    if ftype in RELATIONAL_FIELDS:
        if call.args and isinstance(const(call.args[0]), str):
            comodel = const(call.args[0])
        if ftype == 'One2many' and len(call.args) >= 3 and isinstance(const(call.args[2]), str):
            label = const(call.args[2])
        elif ftype != 'One2many' and len(call.args) >= 2 and isinstance(const(call.args[1]), str):
            label = const(call.args[1])
    elif ftype == 'Selection':
        if len(call.args) >= 2 and isinstance(const(call.args[1]), str):
            label = const(call.args[1])
    else:
        if call.args and isinstance(const(call.args[0]), str):
            label = const(call.args[0])

    flags = []
    for kw in call.keywords:
        if kw.arg == 'comodel_name' and isinstance(const(kw.value), str):
            comodel = const(kw.value)
        elif kw.arg == 'string' and isinstance(const(kw.value), str):
            label = const(kw.value)
        elif kw.arg in ('compute', 'related', 'inverse', 'search'):
            flags.append(f"{kw.arg}={const(kw.value) if isinstance(const(kw.value), str) else ast.unparse(kw.value)}")
        elif kw.arg in ('store', 'required', 'readonly', 'index', 'company_dependent', 'copy', 'tracking', 'check_company') \
                and const(kw.value) not in (None, False):
            flags.append(kw.arg)
        elif kw.arg == 'groups':
            flags.append(f"groups={const(kw.value)}")
    text = f"`{target}` {ftype}" + (f"({comodel})" if comodel else "")
    if label:
        text += f' "{label}"'
    return text + (f" ({', '.join(flags)})" if flags else '')


def map_python(path, module):
    """Markdown lines for one Python file: classes, fields, constraints, sudo, methods."""
    with open(path, encoding='utf-8') as fh:
        source = fh.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"### {rel(path, module)} - cannot parse: {exc}"]
    out = [f"### {rel(path, module)} ({len(source.splitlines())} lines)"]
    doc = first_doc_line(tree)
    if doc:
        out.append(f"_{doc}_")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(f"- L{node.lineno} module function `{node.name}()` - {first_doc_line(node)}".rstrip(' -'))
        if not isinstance(node, ast.ClassDef):
            continue
        attrs, fields, constraints, methods = {}, [], [], []
        for item in node.body:
            if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
                name = item.targets[0].id
                if name in ('_name', '_inherit', '_description', '_order', '_rec_name', '_auto', '_check_company_auto'):
                    attrs[name] = const(item.value)
                elif isinstance(item.value, ast.Call):
                    func_str = ast.unparse(item.value.func)
                    if func_str.startswith('fields.'):
                        fields.append(field_line(name, item.value))
                    elif func_str.endswith(('models.Constraint', 'models.UniqueIndex', 'models.Index')):
                        constraints.append(f"`{name}` {func_str}")
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decs = ', '.join('@' + decorator_name(d) for d in item.decorator_list)
                sudo_n = count_sudo(item)
                parts = [p for p in (decs, 'super()' if calls_super(item) else '', f'sudo x{sudo_n}' if sudo_n else '') if p]
                tags = ' '.join(parts)
                line = f"- L{item.lineno} `{item.name}`" + (f" [{tags}]" if tags else '')
                doc = first_doc_line(item)
                methods.append(line + (f" - {doc}" if doc else ''))
        header = f"**class {node.name}**"
        for key in ('_name', '_inherit', '_description'):
            if attrs.get(key):
                header += f" · {key} = {attrs[key]!r}"
        out.append(header)
        if fields:
            out.append(f"Fields ({len(fields)}): " + '; '.join(fields))
        if constraints:
            out.append(f"Constraints/Indexes ({len(constraints)}): " + '; '.join(constraints))
        out.extend(methods or ['- (no methods)'])
    return out


def map_xml(path, module):
    """Record counts per model, function calls, noupdate and inherited views of one XML file."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return [f"- {rel(path, module)}: cannot parse ({exc})"]
    counts, functions, inherits, noupdate = {}, [], [], False
    for block in root.iter():
        if block.tag in ('data', 'odoo') and block.get('noupdate') in ('1', 'True', 'true'):
            noupdate = True
    for rec in root.iter('record'):
        model = rec.get('model')
        counts[model] = counts.get(model, 0) + 1
        for field in rec.findall('field'):
            if field.get('name') == 'inherit_id' and field.get('ref'):
                inherits.append(field.get('ref'))
    for tag in ('menuitem', 'template'):
        found = len(list(root.iter(tag)))
        if found:
            counts[tag] = found
    for func in root.iter('function'):
        functions.append(f"{func.get('model')}.{func.get('name')}")
    parts = [f"{m} x{n}" for m, n in sorted(counts.items())]
    line = f"- {rel(path, module)}: " + (', '.join(parts) or 'no records')
    if noupdate:
        line += ' · has noupdate'
    if functions:
        line += ' · calls ' + ', '.join(functions)
    if inherits:
        line += ' · inherits ' + ', '.join(sorted(set(inherits)))
    return [line]


def map_access(path, module):
    with open(path, encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))
    out = [f"- {rel(path, module)}: {len(rows)} rows"]
    for row in rows:
        group = row.get('group_id:id') or row.get('group_id/id') or '(no group: all users)'
        rights = ''.join(k[5] for k in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink') if row.get(k) == '1')
        out.append(f"  - {row.get('model_id:id') or row.get('model_id')} · {group} · {rights}")
    return out


def map_module(module):
    out = []
    manifest_path = os.path.join(module, '__manifest__.py')
    with open(manifest_path, encoding='utf-8') as fh:
        manifest = const(ast.parse(fh.read()).body[0].value) or {}
    out.append(f"# {manifest.get('name', os.path.basename(module))} (`{os.path.basename(module)}`)")
    out.append(f"- version {manifest.get('version')} · depends {', '.join(manifest.get('depends', []))}")
    desc = (manifest.get('description') or '').strip()
    has_index_html = os.path.isfile(os.path.join(module, 'static', 'description', 'index.html'))
    out.append('- manifest description: ' + ('set' if desc else ('static/description/index.html present' if has_index_html else 'MISSING (Odoo will render README.* as reStructuredText)')))
    hooks = [f"{k}={manifest[k]}" for k in ('pre_init_hook', 'post_init_hook', 'uninstall_hook') if manifest.get(k)]
    if hooks:
        out.append('- hooks: ' + ', '.join(hooks))
    out.append(f"- data: {', '.join(manifest.get('data', []))}")
    code, tests = [], []
    for path in py_files(module):
        (tests if os.sep + 'tests' + os.sep in path else code).append(path)
    out.append('\n## Python')
    for path in code:
        out.extend(map_python(path, module))
    out.append('\n## Data and views')
    for dirpath, dirnames, filenames in os.walk(module):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if name.endswith('.xml'):
                out.extend(map_xml(path, module))
            elif name.endswith('.csv') and 'security' in dirpath:
                out.extend(map_access(path, module))
    out.append('\n## Tests')
    for path in tests:
        with open(path, encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
        doc = first_doc_line(tree)
        out.append(f"- {rel(path, module)}: {len(names)} tests" + (f" - {doc}" if doc else ''))
    return '\n'.join(out)


CODE_LIKE = re.compile(r'^(?:[a-z_][a-z0-9_]*\.)+[a-z_][a-z0-9_]*(?:\(\))?$|^_?[a-z][a-z0-9_]*_[a-z0-9_]+(?:\(\))?$'
                       r'|^_[a-z][a-z0-9_]*(?:\(\))?$|^[\w./-]+\.(?:py|xml|csv|js|scss)$')


def check_readme(module, readme):
    """List backticked code-like names of README not found in module or active Odoo 19 roots."""
    mod_abs = os.path.abspath(module)
    mod_name = os.path.basename(mod_abs)
    with open(readme, encoding='utf-8') as fh:
        text = fh.read()
    names = sorted({m.strip() for m in re.findall(r'`([^`\n]+)`', text)})

    local_tokens, local_dotted, files = set(), set(), set()
    dotted_re = re.compile(rb'[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+')
    for dirpath, dirnames, filenames in os.walk(mod_abs):
        dirnames[:] = sorted(d for d in dirnames if d not in {'__pycache__', '.git', 'node_modules'})
        for name in filenames:
            files.add(name)
            files.add(rel(os.path.join(dirpath, name), mod_abs))
            if name.endswith(('.py', '.xml', '.csv', '.js')):
                try:
                    data = open(os.path.join(dirpath, name), 'rb').read()
                except OSError:
                    continue
                local_tokens.update(TOKEN_RE.findall(data))
                local_dotted.update(dotted_re.findall(data))

    outside_roots = active_outside_roots(mod_abs)
    addons = {d for base in outside_roots for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))}

    missing, outside = [], []
    pending_outside = {}  # leaf_bytes -> list[name]
    for name in names:
        if not CODE_LIKE.match(name):
            continue
        token = name.removesuffix('()')
        if token.endswith(('.py', '.xml', '.csv', '.js', '.scss')):
            if token in files or os.path.basename(token) in files:
                continue
            missing.append(name)
            continue
        leaf_b = token.split('.')[-1].encode('utf-8')
        tok_b = token.encode('utf-8')
        if tok_b in local_dotted or leaf_b in local_tokens:
            continue
        if token in addons:
            outside.append(name)
            continue
        pending_outside.setdefault(leaf_b, []).append(name)

    if pending_outside:
        needles = set(pending_outside)
        found_outside = set()
        for base in outside_roots:
            if not needles:
                break
            for dirpath, dirnames, filenames in os.walk(base):
                dp_abs = os.path.abspath(dirpath)
                if dp_abs == mod_abs or dp_abs.startswith(mod_abs + os.sep):
                    dirnames[:] = []
                    continue
                dirnames[:] = [
                    d for d in dirnames
                    if d not in SKIP_DIRS and not (d == mod_name and os.path.isfile(os.path.join(dirpath, d, '__manifest__.py')))
                ]
                for fname in filenames:
                    if not fname.endswith(('.py', '.xml', '.js', '.csv')):
                        continue
                    try:
                        data = open(os.path.join(dirpath, fname), 'rb').read()
                    except OSError:
                        continue
                    if not any(n in data for n in needles):
                        continue
                    tokens = set(TOKEN_RE.findall(data))
                    hits = needles & tokens
                    if hits:
                        found_outside |= hits
                        needles -= hits
                        if not needles:
                            break
                if not needles:
                    break
        for leaf_b, name_list in pending_outside.items():
            (outside if leaf_b in found_outside else missing).extend(name_list)

    outside.sort()
    missing.sort()
    print(f"{len(names)} backticked names in {rel(readme, ROOT)}")
    print(f"found only outside this module - Odoo or another addon ({len(outside)}): {', '.join(outside) or '-'}")
    print(f"found nowhere - check these by hand ({len(missing)}): {', '.join(missing) or '-'}")
    return 1 if missing else 0


def main(argv):
    if len(argv) < 2 or not os.path.isfile(os.path.join(argv[1], '__manifest__.py')):
        print(__doc__)
        return 2
    module = os.path.abspath(argv[1])
    if len(argv) == 4 and argv[2] == '--check':
        inside = os.path.join(module, argv[3])
        readme = inside if os.path.isfile(inside) else os.path.abspath(argv[3])
        return check_readme(module, readme)
    print(map_module(module))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
