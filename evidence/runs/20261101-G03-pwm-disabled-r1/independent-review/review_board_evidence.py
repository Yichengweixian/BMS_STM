"""Read existing board evidence only; never imports serial or calls hardware."""
import csv, hashlib, importlib.util, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
PROJECT = Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
ROOT = PROJECT / 'evidence/runs/20261101-G03-pwm-disabled-r1'
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / 'scripts/g03'))
import pwm_disabled as pwm
expected = dict(normal=0, **{'sample-6p5':0, 'adc-stale':8, 'adc-invalid':4,
    'fifo-overrun':16, 'awd-low':32, 'awd-high':32, 'cache-full':65536,
    'heartbeat-expiry':64, 'explicit-stop':1, 'foreground-stall':0, 'bad-crc':2,
    'rx-pressure':2, 'duplicate-start':0, 'conflicting-start':2})
records, failed, checked_files, checked_frames = [], [], 0, 0
for path in sorted(ROOT.glob('board-suite-*/*/result.json')):
    result = json.loads(path.read_text(encoding='utf-8'))
    for name, digest in result['sha256'].items():
        assert hashlib.sha256((path.parent / name).read_bytes()).hexdigest() == digest, str(path.parent / name)
        checked_files += 1
    if result['verdict'] != 'pass':
        assert result['case'] == 'cache-full' and 'start_request_id' not in result
        failed.append(dict(path=str(path.relative_to(ROOT)), error=result['error'], accepted_start=False))
        continue
    status = result['terminal_status']
    assert status['faults'] == expected[result['case']]
    assert status['used'] == status['restored'] == 1
    assert status['owned'] == status['actual_bits'] == status['timer_running'] == 0
    rows = json.loads((path.parent / 'trace.json').read_text())
    assert [r['seq'] for r in rows] == list(range(status['trace_written']))
    counts = {str(event): sum(r['event'] == event for r in rows) for event in range(6)}
    assert counts['0'] == 64 and counts['1'] == counts['3'] == counts['5'] == 1
    assert counts['4'] == int(bool(status['faults']))
    assert all(r['actual_bits'] == 0 for r in rows)
    on = next(r for r in rows if r['event'] == 1)
    off = next(r for r in rows if r['event'] == 3)
    for key in ('rejected_second_start', 'rejected_start_after_clear'):
        rejection = result[key]
        assert rejection['result'] == 4 and rejection['used'] == 1
        assert rejection['start_us'] == status['start_us'] and rejection['stop_us'] == status['stop_us']
        assert rejection['trace_written'] == status['trace_written'] and not rejection['actual_bits']
    assert result['clear']['used'] == 1 and result['clear']['owned'] == 0
    raw_reports = []
    for line in (path.parent / 'serial.bin').read_bytes().splitlines():
        if line.startswith((b'#G3P,', b'#G3E,')):
            raw_reports.append(pwm.parse(line))
            checked_frames += 1
    assert any(r == status for r in raw_reports), 'terminal status not in raw bytes'
    wire_rows = [r for r in raw_reports if r['kind'] == '#G3E' and r['result'] == 0]
    assert wire_rows == rows, 'decoded trace not equal to raw wire records'
    records.append(dict(case=result['case'], path=str(path.relative_to(ROOT)),
        fault_mask=status['faults'], run_us=status['run_us'],
        core_elapsed_us=(status['stop_us']-status['start_us']) & 0xffffffff,
        register_event_elapsed_us=(off['us']-on['us']) & 0xffffffff,
        off_flags=off['flags'], samples=status['sample_count'], raw_min=status['raw_min'], raw_max=status['raw_max'],
        sample_gap_max_us=status['max_sample_gap_us'], irq_gap_max_us=status['max_irq_gap_us'],
        rows=len(rows), overflow=status['trace_overflow'], event_counts=counts,
        cleanup_lag_us=result['analysis'].get('foreground_cleanup_after_off_us'),
        preflight_first_to_start_us=result['analysis']['preflight_first_to_start_us']))
assert {r['case'] for r in records} == set(expected) and len(records) == 15
source = json.loads((ROOT/'production-source-manifest.json').read_text())
keys = {'g03_pwm_port.c', 'pwm_oneshot.c'}
core_port = {r['path']: r['sha256'] for r in source['files'] if Path(r['path']).name in keys}
for relative, digest in core_port.items():
    assert hashlib.sha256((PROJECT/relative).read_bytes()).hexdigest() == digest
spec = importlib.util.spec_from_file_location('recovery_review', PROJECT/'scripts/g03/post_pwm_recovery.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
folder = ROOT/'resource-recovery-01'
restored = json.loads((folder/'result.json').read_text())
assert restored['verdict'] == 'pass'
for name,digest in restored['sha256'].items():
    assert hashlib.sha256((folder/name).read_bytes()).hexdigest() == digest
    checked_files += 1
wire_reports, wire_g01 = [], []
for line in (folder/'serial.bin').read_bytes().splitlines():
    if line.startswith((b'#G3P,',b'#G3E,',b'#G02,',b'#G3R,',b'#G3S,')):
        wire_reports.append(recovery.parse_report(line)); checked_frames += 1
    elif line.startswith(b'M,'):
        wire_g01.append(recovery.g01.parse_line(line))
assert wire_reports == json.loads((folder/'reports.json').read_text())
device = list(csv.DictReader((folder/'g01.csv').open(newline='',encoding='utf-8')))
assert [{k:r[k] for k in recovery.g01.FIELDS} for r in device] == wire_g01
capture = [r for r in device if r['phase']=='g01-15s']
summary = recovery.summarize_g01(capture)
assert summary['verdict'] == 'pass'
assert all(summary[key] == restored['g01'][key] for key in summary)
assert len(capture) == 270 and summary['complete_groups'] == 30
assert all(r['physical_valid']=='0' and r['raw_valid']=='1' for r in capture)
relay_rows = json.loads((folder/'relay-dry-samples.json').read_text())
assert [r for r in wire_reports if r['kind']=='#G3S'] == relay_rows
assert recovery.relay.analyze(restored['relay_final'],relay_rows) == restored['relay_analysis']
assert all(r['bits']==0 for r in relay_rows)
assert restored['g02_sample']['updates'] == restored['g02_sample']['completions'] == 99997
assert restored['g02_sample']['adc_errors'] == restored['g02_sample']['overruns'] == 0
for name in ('initial_pwm','pwm_after_g02','final_pwm'):
    recovery.stopped_pwm(restored[name])
assert restored['initial_pwm']['start_id'] == restored['final_pwm']['start_id']
assert restored['start_attempts'] == [1,31]
recovery_summary = dict(verdict='pass', capture_rows=len(capture),complete_groups=summary['complete_groups'],
    channel_count=len(summary['channels']),raw_valid_rows=sum(r['raw_valid']=='1' for r in capture),
    g02_updates=99997,g02_completions=99997,relay_rows=len(relay_rows),
    relay_analysis=restored['relay_analysis'],direct_tim2_register_readback=False,
    final_used=restored['final_pwm']['used'], final_owned=restored['final_pwm']['owned'],
    final_restored=restored['final_pwm']['restored'], final_output_bits=restored['final_pwm']['actual_bits'])
result = dict(verdict='pass', hardware_access=False, scope='read-only audit of completed disabled cases',
    matched_scenario_count=len(records), checked_artifact_hashes=checked_files, parsed_raw_reply_frames=checked_frames,
    source_sha256=core_port, preserved_failed_setup=failed, cases=records,recovery=recovery_summary,
    physical_valid=0, physical_output_tested=False,
    remaining_board_recovery=None)
(OUT/'board-review-data.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='cases'}, indent=2))
