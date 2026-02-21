"""Concatenate all omega v13 source files into a single markdown for external analysis."""
import pathlib, datetime

ROOT = pathlib.Path(r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\1_silver\projects\omega_v13_microkernel')
OUT  = ROOT / f'OMEGA_V13_CONCAT_{datetime.date.today()}.md'

SKIP_DIRS  = {'node_modules', 'dist', 'exemplars', 'test-results', 'reports', '.git'}
SKIP_FILES = {'package-lock.json'}
INCLUDE_EXT = {'.ts', '.tsx', '.mjs', '.json', '.html', '.md', '.scxml'}
SKIP_NAMES  = {OUT.name}  # don't include the output file itself

def want(p: pathlib.Path) -> bool:
    if p.name in SKIP_NAMES:
        return False
    if p.name in SKIP_FILES:
        return False
    return p.suffix in INCLUDE_EXT

files = []
for p in sorted(ROOT.rglob('*')):
    if any(skip in p.parts for skip in SKIP_DIRS):
        continue
    if not p.is_file():
        continue
    if want(p):
        files.append(p)

fence = '```'
lines = [
    f'# OMEGA V13 SOURCE CONCAT — {datetime.datetime.utcnow().isoformat()}Z',
    f'# Root: {ROOT}',
    f'# Files: {len(files)}',
    '',
]

for p in files:
    rel = p.relative_to(ROOT)
    lang = p.suffix.lstrip('.')
    if lang == 'mjs':
        lang = 'js'
    lines.append('---')
    lines.append(f'## FILE: {rel}')
    lines.append(f'{fence}{lang}')
    try:
        lines.append(p.read_text(encoding='utf-8', errors='replace'))
    except Exception as e:
        lines.append(f'[ERROR READING: {e}]')
    lines.append(fence)
    lines.append('')

OUT.write_text('\n'.join(lines), encoding='utf-8')
size = OUT.stat().st_size
print(f'Written : {OUT.name}')
print(f'Size    : {size / 1024:.1f} KB')
print(f'Files   : {len(files)}')
for f in files:
    print(f'  {f.relative_to(ROOT)}')
