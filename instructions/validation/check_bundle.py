"""Validate documentation only. No firmware build, instrument, or hardware access."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def snapshot():
    paths = [
        WORKSPACE / name for name in [
            'docs/course/基于STM32N6的智能BMS边缘智能系统设计.pptx',
            'docs/course/任务2恒流控制实验_实验步骤.docx', 'docs/manuals/BMS_EX工程模板使用说明.docx',
            'docs/manuals/BMS电池测试上位机操作手册（图文版）.docx', 'firmware/prebuilt/BMS_Appli.hex',
            'BMS_EXv1.1/BMS_EX/Appli/Core/Src/main.c',
            'BMS_EXv1.1/BMS_EX/BSP/pi.h', 'BMS_EXv1.1/BMS_EX/BSP/pi.c',
            'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/BMS_EX_Appli.uvprojx',
            'BMS_EXv1.1/BMS_EX/README.md',
            'BMS_EXv1.1/BMS_EX/MDK-ARM/Keil_Debug_Release_配置说明.md',
        ]
    ]
    paths += sorted((WORKSPACE / 'BMS_EXv1.1/BMS_EX').glob('*.ioc'))
    old = Path('D:/ADMIN/Desktop/instructions')
    names = ['README.md', 'AGENTS.md', 'CLAUDE.md', 'STATUS.md',
             'specs/agent-policy.md', 'specs/data.md', 'specs/methods.md',
             'specs/claims.md', 'specs/roadmap.md',
             'implementation/00-work-breakdown.md',
             'implementation/05-protocol-adapter.md',
             'implementation/06-validation-delivery.md', 'prompts/03-audit.md',
             'references/open-questions.md', 'validation/structure-report.json',
             'validation/review-notes.md']
    paths += [old / n for n in names]
    paths += sorted((old / 'studies/_TEMPLATE').glob('*.md'))
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise RuntimeError(f'Source missing: {missing}')
    obj = {
        'schema_version': '1.0',
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Selected consulted inputs; not a complete build source snapshot.',
        'files': [{'path': p.as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in paths],
    }
    (ROOT / 'references/source-manifest.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def check():
    issues = []
    json_count = 0
    for p in ROOT.rglob('*.json'):
        if p.name == 'structure-report.json':
            continue
        try:
            obj = json.loads(p.read_text(encoding='utf-8'))
            json_count += 1
            if obj.get('is_template') and (obj.get('verdict') is not None or obj.get('status') != 'not_started'):
                issues.append(f'Template has execution result: {p}')
        except Exception as exc:
            issues.append(f'Invalid JSON: {p}: {exc}')
    links = 0
    for p in ROOT.rglob('*.md'):
        text = p.read_text(encoding='utf-8')
        text = re.sub(r'```.*?```', '', text, flags=re.S)
        for dest in re.findall(r'\]\((<[^>]+>|[^\s)]+)\)', text):
            dest = unquote(dest.strip('<>'))
            if dest.startswith(('http://', 'https://', '#', 'mailto:')):
                continue
            dest = dest.split('#')[0]
            if re.match(r'^/[A-Za-z]:/', dest):
                dest = dest[1:]
            target = Path(dest) if re.match(r'^[A-Za-z]:', dest) else p.parent / dest
            links += 1
            if not target.exists():
                issues.append(f'Broken local link: {p.relative_to(ROOT)} -> {dest}')
    manifest = ROOT / 'references/source-manifest.json'
    count = 0
    if manifest.exists():
        for entry in json.loads(manifest.read_text(encoding='utf-8'))['files']:
            p = Path(entry['path'])
            count += 1
            if not p.exists() or sha(p) != entry['sha256']:
                issues.append(f'Source changed or missing: {p}')
    else:
        issues.append('No source manifest')
    if not (ROOT / 'BMS实施与验收指南.html').is_file():
        issues.append('No rendered HTML')
    report = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': ['json_parse', 'template_unexecuted_state', 'local_markdown_links', 'selected_source_hashes', 'html_exists'],
        'firmware_built': False, 'hardware_experiments_executed': False,
        'json_files_checked': json_count, 'local_links_checked': links,
        'source_hashes_checked': count, 'issues': issues,
        'passed': not issues,
    }
    (ROOT / 'validation/structure-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if issues else 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', action='store_true', help='Capture selected current input hashes before checking.')
    args = parser.parse_args()
    if args.snapshot:
        snapshot()
    raise SystemExit(check())
