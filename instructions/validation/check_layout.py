"""Check relocation integrity and active entry points; no build or hardware access."""
import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.ids = set()
        self.rows = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.add(a['id'])
        if tag == 'a' and 'href' in a:
            self.hrefs.append(a['href'])
        if tag == 'tr' and 'data-category' in a:
            self.rows += 1

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()

issues = []
migration = json.loads((ROOT/'references/layout-migration.json').read_text(encoding='utf-8-sig'))
for item in migration['untouched_keil_files']:
    p = WORKSPACE/item['path']
    if not p.is_file() or digest(p) != item['sha256']:
        issues.append('Keil baseline changed or missing: '+item['path'])
unmodified = 0
for item in migration['relocated_files']:
    p = WORKSPACE/item['after']
    if p.suffix.lower() == '.html':
        continue
    unmodified += 1
    if not p.is_file() or digest(p) != item['sha256_before']:
        issues.append('Moved source changed or missing: '+item['after'])

pages = [ROOT/'BMS实施与验收指南.html', WORKSPACE/'docs/guides/BMS系统原理与开发路线.html', WORKSPACE/'docs/guides/目录逐文件说明.html']
html_links = 0
inventory_rows = 0
for p in pages:
    parser = Links()
    parser.feed(p.read_text(encoding='utf-8'))
    if p.name == '目录逐文件说明.html':
        inventory_rows = parser.rows
    for href in parser.hrefs:
        u = urlparse(href)
        if u.scheme in ['http','https','mailto','data']:
            continue
        if not u.path:
            if u.fragment and unquote(u.fragment) not in parser.ids:
                issues.append(f'Missing anchor: {p.name} -> {href}')
            continue
        value = unquote(u.path)
        if re.match(r'^/[A-Za-z]:/',value):
            value=value[1:]
        target = Path(value) if u.scheme == 'file' or re.match(r'^[A-Za-z]:',value) else p.parent/value
        html_links += 1
        if not target.is_file():
            issues.append(f'Broken HTML link: {p.name} -> {href}')

md_links = 0
for p in [WORKSPACE/'README.md',WORKSPACE/'AGENTS.md']:
    text=p.read_text(encoding='utf-8')
    for dest in re.findall(r'\]\((<[^>]+>|[^\s)]+)\)',text):
        value=unquote(dest.strip('<>')).split('#')[0]
        if value.startswith(('http:','https:')):
            continue
        md_links += 1
        if not (p.parent/value).exists():
            issues.append(f'Broken entry link: {p.name} -> {value}')

inventory = pages[-1].read_text(encoding='utf-8')
import html
listed = [html.unescape(x) for x in re.findall(r'<td class="path">(.*?)</td>',inventory)]
for rel in listed:
    if not (WORKSPACE/rel).is_file() and not Path(rel).name.startswith('~$'):
        issues.append('Inventory target missing: '+rel)
if len(listed) != len(set(listed)):
    issues.append('Duplicate inventory paths')

root_items=[p.name for p in WORKSPACE.iterdir()]
lock_files=[p.relative_to(WORKSPACE).as_posix() for p in WORKSPACE.rglob('~$*') if p.is_file()]
report={
    'checked_at_utc':datetime.now(timezone.utc).isoformat(),
    'scope':['unchanged_keil_files','relocated_source_hashes','root_entry_links','three_active_html_local_links','inventory_targets'],
    'keil_files_verified':len(migration['untouched_keil_files']),
    'relocated_original_files_verified':unmodified,
    'intentionally_updated_moved_html':2,
    'html_local_links_checked':html_links,'root_markdown_links_checked':md_links,
    'inventory_rows':inventory_rows,'root_items':root_items,'office_lock_files_left_in_place':lock_files,
    'firmware_built':False,'hardware_experiments_executed':False,'issues':issues,'passed':not issues,
}
(ROOT/'validation/layout-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(1 if issues else 0)
