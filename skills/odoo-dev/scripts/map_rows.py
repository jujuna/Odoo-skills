"""Print the coupling-map rows that mention a business object, model, field, module or row ID.

Usage (from the odoo19 root):
    python3 .claude/skills/odoo-dev/scripts/map_rows.py <term> [<term> ...]

Each matching line of references/coupling-map.md is printed whole, with its line number and the section
it sits in. Terms are matched without case; a term such as T7 or R2 also finds the rows that cite that ID.
A term with no row is reported: that means the map has nothing, not that nothing reads the object.
"""
import re
import sys
from pathlib import Path

MAP = Path(__file__).resolve().parents[1] / 'references/coupling-map.md'


def main():
    terms = sys.argv[1:]
    if not terms:
        sys.exit(__doc__)
    lines = MAP.read_text(encoding='utf-8').splitlines()
    for term in terms:
        pattern = re.compile(rf'(?<!\w){re.escape(term)}(?!\w)', re.IGNORECASE)
        section, printed, count = '', None, 0
        print(f'===== {term}')
        for number, line in enumerate(lines, 1):
            if line.startswith('## '):
                section = line
            elif pattern.search(line):
                if printed != section:
                    print(f'\n{section}')
                    printed = section
                print(f'{number}: {line}')
                count += 1
        print(f'\n{count} line(s) for {term!r}' if count else f'no row mentions {term!r}: the map has nothing on it')


if __name__ == '__main__':
    main()
