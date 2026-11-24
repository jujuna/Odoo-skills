"""Dependency sweep: every place that names a method, field, model, view or module.

Usage (from the odoo19 root):
    python3 .claude/skills/odoo-dev/scripts/sweep.py method|field|model|view|module <name> [--roots <folder> ...] [--all]

It runs the search patterns of the odoo-scout sweep table over the active Odoo 19 roots
(custom_addons/gec_odoo_modules, custom_addons/alta_hr_customization, plus any odoo.conf addons_path roots,
and addons, enterprise, odoo), walking them itself so folders listed in .git/info/exclude are never skipped.
Every line that names the target as a whole word and fits no pattern is listed under "other mentions".
Not searched by default: i18n, lib, node_modules, and sibling client project folders under custom_addons/
unless explicitly passed via --roots.
"""
import argparse
import configparser
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(os.environ.get('CLAUDE_PROJECT_DIR') or Path.cwd()).resolve()
SKIP_DIRS = {'i18n', 'i18n_extra', 'node_modules', '__pycache__', '.git', 'lib'}


def default_roots():
    conf = ROOT / 'odoo.conf'
    roots = []
    if conf.is_file():
        cp = configparser.ConfigParser(interpolation=None)
        try:
            cp.read(conf, encoding='utf-8')
            raw = cp.get('options', 'addons_path', fallback='')
            for part in raw.split(','):
                p = Path(part.strip())
                if not p:
                    continue
                if not p.is_absolute():
                    p = (ROOT / p).resolve()
                try:
                    rel = str(p.relative_to(ROOT))
                except ValueError:
                    rel = str(p)
                if p.is_dir() and rel not in roots:
                    roots.append(rel)
        except (OSError, configparser.Error):
            pass
    for base in ('custom_addons/gec_odoo_modules', 'custom_addons/alta_hr_customization', 'addons', 'enterprise', 'odoo'):
        if (ROOT / base).is_dir() and base not in roots:
            roots.append(base)
    return roots


ROOTS = default_roots()
SUFFIXES = ('.py', '.xml', '.js', '.csv')
OTHER = 'other mentions'
LIST_LIMIT = 300


def patterns(kind, name):
    n, dotted, underscored = re.escape(name), re.escape(name), re.escape(name.replace('.', '_'))
    table = {
        'method': {
            'defined or overridden': (rf'def {n}\b', ('.py',)),
            'called': (rf'\.{n}\(', ('.py', '.js')),
            'named as text (buttons, crons, getattr, server actions)': (rf'''['"]{n}['"]''', ('.py', '.xml', '.js', '.csv')),
        },
        'field': {
            'defined': (rf'^\s*{n}\s*=\s*fields\.', ('.py',)),
            'attribute access': (rf'\.{n}\b', ('.py', '.js')),
            'named as text (depends, domains, vals, related)': (rf'''['"]([\w.]+\.)?{n}(\.[\w.]+)?['"]''', ('.py', '.js', '.csv')),
            'in views, reports and data': (rf'''(name|field|t-field|t-out|t-esc|t-if|t-att[\w-]*|domain|context|invisible|readonly|required)=["'][^"']*\b{n}\b''', ('.xml',)),
        },
        'model': {
            'defined or inherited': (rf'''_(name|inherit|inherits)\s*=.*['"]{dotted}['"]''', ('.py',)),
            'used in code': (rf'''env\[['"]{dotted}['"]\]|['"]{dotted}['"]''', ('.py', '.js')),
            'in views and data': (rf'''(model|res_model|comodel_name|relation)=["']{dotted}["']|>{dotted}<''', ('.xml',)),
            'access rows and xmlids': (rf'\b{dotted}\b|model_{underscored}\b', ('.csv', '.xml')),
        },
        'view': {
            'inherited or referenced': (rf'''(inherit_id|ref|t-inherit|t-call|action|parent|menu)\s*=\s*["'](%\()?([\w_]+\.)?{n}\b|ref\(['"]([\w_]+\.)?{n}['"]\)''', ('.xml', '.py', '.js')),
        },
        'module': {
            'in a manifest': (rf'''['"]{n}['"]''', ('__manifest__.py',)),
            'imported or referenced by xmlid': (rf'odoo\.addons\.{n}\b|\b{n}\.[a-z_0-9]+', ('.py', '.xml', '.js', '.csv')),
        },
    }
    word = rf'(?<![\w.]){dotted}(?![\w.])' if kind == 'model' else rf'(?<!\w){n}(?!\w)'
    return {**table[kind], OTHER: (word, SUFFIXES)}


def module_of(path):
    parts = path.relative_to(ROOT).parts
    for index in range(len(parts) - 1, 0, -1):
        if (ROOT.joinpath(*parts[:index]) / '__manifest__.py').exists():
            return '/'.join(parts[:index])
    return '/'.join(parts[:2])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=['method', 'field', 'model', 'view', 'module'])
    parser.add_argument('name')
    parser.add_argument('--roots', nargs='+', default=ROOTS)
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()

    wanted = patterns(args.kind, args.name)
    compiled = {label: (re.compile(regex.encode()), suffixes) for label, (regex, suffixes) in wanted.items()}
    needle = args.name.split('.')[-1].encode() if args.kind != 'model' else args.name.replace('.', '_').encode()
    plain = args.name.encode()
    hits = {label: [] for label in wanted}
    for root in args.roots:
        target_root = ROOT / root
        if not target_root.is_dir():
            continue
        for folder, dirs, files in os.walk(target_root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for filename in files:
                labels = [label for label, (_, suffixes) in compiled.items() if filename.endswith(suffixes)]
                if not labels:
                    continue
                path = Path(folder) / filename
                data = path.read_bytes()
                if needle not in data and plain not in data:
                    continue
                for number, line in enumerate(data.splitlines(), 1):
                    matched = [label for label in labels if label != OTHER and compiled[label][0].search(line)]
                    if not matched and OTHER in labels and compiled[OTHER][0].search(line):
                        matched = [OTHER]
                    for label in matched:
                        hits[label].append((path, number, line.decode('utf-8', 'replace').strip()))

    print(f'Sweep {args.kind} {args.name!r} in {", ".join(args.roots)}')
    print('Not searched: i18n, lib, node_modules, and unnamed custom_addons/ project folders')
    for label, (regex, suffixes) in wanted.items():
        found = hits[label]
        print(f'\n== {label}: {len(found)} hits   pattern: {regex}   files: {", ".join(suffixes)}')
        for module, count in sorted(Counter(module_of(path) for path, _, _ in found).items()):
            print(f'   {count:5d}  {module}')
        shown = found if args.all else found[:LIST_LIMIT]
        for path, number, code in shown:
            print(f'{path.relative_to(ROOT)}:{number}: {code[:400]}')
        if len(shown) < len(found):
            print(f'   ... {len(found) - len(shown)} more hits not listed: rerun with --all or narrow --roots')
    if not any(hits.values()):
        print('\nNo hit for any pattern.')
        sys.exit(1)


if __name__ == '__main__':
    main()
