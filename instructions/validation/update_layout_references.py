"""Refresh documentation after the recorded layout migration; never edits firmware."""
import hashlib
import html
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
HISTORY = ROOT / 'references/history'
MIGRATION = json.loads((ROOT / 'references/layout-migration.json').read_text(encoding='utf-8-sig'))
MAPPING = {x['before']: x['after'] for x in MIGRATION['mappings']}

def relocated(relative):
    for old, new in MAPPING.items():
        if relative == old or relative.startswith(old + '/'):
            return new + relative[len(old):]
    return relative

def preserve_validation():
    out = HISTORY / 'validation-before-layout'
    out.mkdir(exist_ok=True)
    for name in ['structure-report.json', 'html-report.json', 'desktop.png', 'acceptance.png', 'mobile.png']:
        source = ROOT / 'validation' / name
        if source.exists() and not (out / name).exists():
            shutil.copy2(source, out / name)

def refresh_manifest():
    old = json.loads((HISTORY / 'source-manifest.before-layout.json').read_text(encoding='utf-8'))
    for entry in old['files']:
        p = Path(entry['path'])
        try:
            rel = p.relative_to(WORKSPACE).as_posix()
        except ValueError:
            continue
        target = WORKSPACE / relocated(rel)
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry['sha256']:
            raise RuntimeError(f'Source changed during relocation: {target}')
        if p != target:
            entry['previous_path'] = entry['path']
        entry['path'] = target.as_posix()
    old['previous_captured_at_utc'] = old['captured_at_utc']
    old['captured_at_utc'] = datetime.now(timezone.utc).isoformat()
    old['layout_migration'] = 'layout-migration.json'
    old['scope'] = 'Selected consulted inputs after relocation; bytes verified against the preserved pre-layout snapshot; not a complete build source snapshot.'
    (ROOT / 'references/source-manifest.json').write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding='utf-8')

def refresh_teaching():
    output = WORKSPACE / 'docs/guides/BMS系统原理与开发路线.html'
    text = (HISTORY / 'BMS系统原理与开发路线.before-layout.html').read_text(encoding='utf-8')
    def replace_link(match):
        href = html.unescape(match.group(1))
        if href.startswith(('#', 'http:', 'https:', 'mailto:', 'data:')):
            return match.group(0)
        src = unquote(href)
        target = WORKSPACE / relocated(src)
        if not target.is_file():
            raise RuntimeError(f'Cannot resolve old link: {href}')
        new = Path(os.path.relpath(target, output.parent)).as_posix()
        return 'href="' + html.escape(new, quote=True) + '"'
    text = re.sub(r'href="([^"]+)"', replace_link, text)
    text = text.replace('顶层HEX', '预编译HEX').replace('顶层 HEX', '预编译 HEX').replace('烧顶层 ', '烧预编译固件 ')
    output.write_text(text, encoding='utf-8')

DESCRIPTIONS = {
    'AGENTS.md': '已采用的BMS项目代理执行入口；读取规范、尊重实验边界并维护证据链。',
    'README.md': '项目导航，说明目录用途、规范入口、Keil工程和当前实施状态。',
    'instructions/README.md': 'BMS执行规范入口；流程已采用，工程建议阈值仍待正式实验冻结。',
    'instructions/AGENTS_BMS.example.md': '原入口示例的采用说明；当前执行入口在项目根AGENTS.md。',
    'instructions/guide.md': '采样、标定、开环/闭环、SOC和实施次序的解释源文档。',
    'instructions/BMS实施与验收指南.html': '由规范Markdown生成的离线阅读版，含阶段验收、数据与迁移说明。',
    'instructions/MIGRATION.md': '其他工程instructions如何适配到BMS的取舍，不继承外部指令。',
    'instructions/WORKFLOW.md': '探索与正式验收、冻结、证据、状态和变更影响规则。',
    'instructions/STATUS.md': '项目阶段进度唯一人工维护入口；硬件结果保持未验证。',
    'instructions/RUNLOG.md': '按时间追加的关键动作与结论，保存规范创建和本次整理经过。',
    'instructions/specs/acceptance.md': 'G00—G07前置、方法、指标、证据、失败回退与课程来源。',
    'instructions/specs/measurement.md': '芯片驱动、板级换算/标定与上层控制的职责和公式。',
    'instructions/specs/data.md': '原始数据、时间戳、独立参考、SOC标签和训练划分规范。',
    'instructions/specs/hardware-profile.json': '实物参数和允许测试边界的唯一配置记录；未知项为null。',
    'instructions/templates/work-card.md': '问题、设计、判据、执行、结果五部分合一的未执行模板。',
    'instructions/templates/run-manifest.json': '每次运行的固件、配置、仪器、条件和原始证据记录模板。',
    'instructions/templates/calibration-record.json': '通道标定系数、适用范围、参考和独立验证模板。',
    'instructions/references/source-map.md': '课程、源码和官方参考的定位及证据适用范围。',
    'instructions/references/source-manifest.json': '按新路径记录的已核对资料SHA-256清单，保留原采集时间与旧路径关联。',
    'instructions/references/open-questions.md': '未确认硬件与需求事实、所需证据和具体阻塞范围。',
    'instructions/references/layout-migration.json': '本次移动映射、13份原始文件前后哈希及432份原工程文件基线。',
    'instructions/validation/check_bundle.py': '检查规范JSON、模板状态、Markdown链接与资料哈希，不构建固件。',
    'instructions/validation/render_html.cjs': '从规范Markdown生成BMS实施与验收指南HTML。',
    'instructions/validation/review_html.cjs': '使用无头浏览器核对规范HTML导航、链接和移动端布局。',
    'instructions/validation/organize_layout.ps1': '本次一次性目录迁移脚本；校验路径边界，禁止覆盖，不删除文件。',
    'instructions/validation/update_layout_references.py': '从保留快照更新搬迁链接、源码清单及当前逐文件说明。',
    'instructions/validation/check_layout.py': '核对原工程与移动资料哈希、根入口及三份HTML的本地链接。',
    'docs/guides/BMS系统原理与开发路线.html': '系统原理说明，含ADC/PWM/PI交互示例；本次只修正搬迁路径。',
}

def refresh_inventory():
    original = (HISTORY / '目录逐文件说明.before-layout.html').read_text(encoding='utf-8')
    row_pattern = re.compile(r'<tr data-category="([^"]+)"><td class="path">(.*?)</td><td>.*?</td><td>(.*?)</td><td class="size">.*?</td></tr>', re.S)
    existing = {}
    for cat, oldpath, desc in row_pattern.findall(original):
        key = relocated(html.unescape(oldpath))
        existing[key] = (cat.replace('顶层资料与工具','资料与工具'), desc)
    output = WORKSPACE / 'docs/guides/目录逐文件说明.html'
    files = sorted(p for p in WORKSPACE.rglob('*') if p.is_file() and p != output
                   and not any(part in {'.git', 'node_modules', '.venv'} for part in p.relative_to(WORKSPACE).parts))
    rows = []
    categories = set()
    for p in files:
        rel = p.relative_to(WORKSPACE).as_posix()
        if rel in existing:
            cat, desc = existing[rel]
        elif rel in DESCRIPTIONS:
            cat = '项目入口' if '/' not in rel else ('阅读指南' if rel.startswith('docs/') else '执行规范')
            desc = html.escape(DESCRIPTIONS[rel])
        elif '/history/' in rel:
            cat, desc = '历史快照', '目录整理前的说明、来源清单或检查快照；保留历史路径和结果，不作为当前执行入口。'
        elif p.name.startswith('~$'):
            cat, desc = '临时与备份', 'Office生成的临时锁文件，由Office管理；本次不移动或删除，存在状态可能变化。'
        elif rel.startswith('instructions/validation/'):
            cat = '文档检查'
            desc = '文档结构或HTML布局的检查报告/截图，只说明文档状态，不是硬件实验结果。'
        else:
            cat, desc = '待补充说明', '本次目录快照检测到的文件；尚未进行内容级审查。'
        categories.add(cat)
        rows.append(f'<tr data-category="{html.escape(cat)}"><td class="path">{html.escape(rel)}</td><td>{html.escape(cat)}</td><td>{desc}</td><td class="size">{p.stat().st_size:,}</td></tr>')
    # Only replace the inventory table, preserving every original source explanation.
    text = re.sub(r'(<table id="files">.*?<tbody>).*?(</tbody>)', lambda m:m.group(1)+'\n'.join(rows)+m.group(2), original, flags=re.S)
    text = re.sub(r'(<select id="category"[^>]*>).*?(</select>)', lambda m:m.group(1)+'<option value="">全部分类</option>'+''.join(f'<option>{html.escape(c)}</option>' for c in sorted(categories))+m.group(2), text, flags=re.S)
    text = re.sub(r'<p><strong>阅读范围：</strong>.*?</p>', f'<p><strong>阅读范围：</strong>本次目录快照列出 {len(files)} 个文件（含历史快照与临时锁文件，不含本报告自身）。原工程逐文件说明保留，新增规范与导航文件补充用途。目录已整理，原代码、课程文档、压缩包与固件未改内容；HTML路径与规范入口已更新。本次没有重新编译、安装、烧录或上板。临时文件数量可能随Office状态变化。</p>', text, flags=re.S)
    text = text.replace('原有文件逐项用途', '当前目录文件逐项用途')
    text = text.replace('PPT 与任务2/3讲义', 'docs/course中的PPT与任务2步骤')
    text = text.replace('顶层 BMS_Appli.hex + BMS上位机d.zip + 上位机手册', 'firmware/prebuilt/BMS_Appli.hex + tools/host/BMS上位机d.zip + docs/manuals中的上位机手册')
    text = text.replace('再完成电流 ADC 标定、闭环、限幅与停机逻辑', '在已完成电流ADC标定与停止验证的基础上，接入闭环、限幅与换向逻辑')
    insert = '<p><strong>当前入口：</strong><a href="../../README.md">项目导航</a> · <a href="../../instructions/README.md">执行规范</a> · <a href="../../instructions/BMS实施与验收指南.html">实施与验收指南</a>。根目录AGENTS.md已采用BMS流程；具体实验阈值与硬件参数仍按规范确认。</p>'
    text = text.replace('<h2>当前实际运行链路</h2>', insert+'<h2>当前实际运行链路</h2>')
    output.write_text(text, encoding='utf-8')
    return len(files)

if __name__ == '__main__':
    preserve_validation()
    refresh_manifest()
    refresh_teaching()
    renderer = ROOT / 'validation/render_html.cjs'
    text = renderer.read_text(encoding='utf-8').replace('说明源文件与模板位于 BMS执行规范', '说明源文件与模板位于 instructions')
    renderer.write_text(text, encoding='utf-8')
    print(json.dumps({'indexed_files':refresh_inventory(), 'source_hashes_verified':True}, ensure_ascii=False))
