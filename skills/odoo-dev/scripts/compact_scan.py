"""List the compact-code.md and ai-smells.md candidates of a module, with path:line.

Usage (any Python 3.10+, no Odoo needed):
    python compact_scan.py <dir or .py file> [...] [--width 120] [--stats]

Reports: statements written over several lines that fit in --width characters when joined,
module docstrings, docstrings over three lines, hasattr(), except Exception and backslash
continuations. Tests, migrations, manifests and __init__.py are skipped. --stats prints the
per-1000-lines summary instead of the hits. A hit is a candidate: ai-smells.md says which are
real.
"""
import argparse
import ast
import re
from pathlib import Path

COMPOUND = (ast.If, ast.While, ast.For, ast.With, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def joined_len(lines):
    out = lines[0].rstrip().rstrip('\\').rstrip()
    for line in lines[1:]:
        part = line.strip().rstrip('\\').strip()
        sep = '' if out.endswith(('(', '[', '{')) or part.startswith((')', ']', '}')) else ' '
        out += sep + part
    return len(re.sub(r',\s*([)\]}])', r'\1', out))


def statement_lines(node, lines):
    """Lines of a simple statement, or of a compound statement's header only."""
    if isinstance(node, COMPOUND):
        first = node.body[0]
        end = min([first.lineno] + [d.lineno for d in getattr(first, 'decorator_list', [])]) - 1
        seg = lines[node.lineno - 1:end]
        while seg and (not seg[-1].strip() or seg[-1].lstrip().startswith(('#', '"""', "'''"))):
            seg.pop()
        return seg
    if isinstance(node, ast.stmt):
        return lines[node.lineno - 1:node.end_lineno]
    return []


def scan(path, width):
    src = path.read_text(errors='ignore')
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [], 0
    lines = src.splitlines()
    hits = []
    if ast.get_docstring(tree):
        hits.append((1, 'module-docstring', ''))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            if doc and len(doc.strip().splitlines()) > 3:
                hits.append((node.body[0].lineno, 'long-docstring', f'{len(doc.strip().splitlines())} lines'))
        seg = statement_lines(node, lines)
        if len(seg) < 2:
            continue
        text = '\n'.join(seg)
        if '#' in text or '"""' in text or "'''" in text:
            continue
        size = joined_len(seg)
        if size <= width:
            hits.append((node.lineno, 'needless-split', f'{len(seg)} lines -> {size} chars'))
    for no, line in enumerate(lines, 1):
        code = line.split('#', 1)[0]
        if 'hasattr(' in code:
            hits.append((no, 'hasattr', line.strip()))
        if re.search(r'except (Exception|BaseException)\b|except\s*:', code):
            hits.append((no, 'broad-except', line.strip()))
        if code.rstrip().endswith('\\'):
            hits.append((no, 'backslash', line.strip()))
    return hits, sum(1 for line in lines if line.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dirs', nargs='+')
    parser.add_argument('--width', type=int, default=120)
    parser.add_argument('--stats', action='store_true')
    args = parser.parse_args()
    for root in args.dirs:
        paths = [Path(root)] if Path(root).is_file() else Path(root).rglob('*.py')
        files = sorted(p for p in paths
                       if not {'tests', 'migrations'} & set(p.parts) and p.name not in ('__init__.py', '__manifest__.py'))
        counts, loc = {}, 0
        for path in files:
            hits, size = scan(path, args.width)
            loc += size
            for no, kind, detail in sorted(hits):
                counts[kind] = counts.get(kind, 0) + 1
                if not args.stats:
                    print(f'{path}:{no}  {kind}  {detail}')
        kloc = max(loc, 1) / 1000
        summary = '  '.join(f'{k}={v} ({v / kloc:.1f}/kloc)' for k, v in sorted(counts.items()))
        print(f'# {root}: {len(files)} files, {loc} lines  {summary}')


if __name__ == '__main__':
    main()
