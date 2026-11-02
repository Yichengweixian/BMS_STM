"""Offline G01 statistics and candidate voltage calibration. Never writes firmware.

Python 3.8+, standard library. See instructions/specs/G01-voltage-tools.md.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

from g01_capture import CHANNELS, FIELDS, parse_line

CELLS = ('cell1', 'cell7', 'cell13')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('non-finite number')
    return result


def load_capture(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'g01-recorder-v1':
        raise ValueError('unsupported capture schema')
    manifest['sha256'] = {k.replace('\\', '/'): v for k, v in manifest.get('sha256', {}).items()}
    for name in ('raw/serial.bin', 'raw/events.jsonl', 'derived/device.csv'):
        expected = manifest['sha256'].get(name)
        if expected is None or sha(folder / name) != expected:
            raise ValueError('capture hash mismatch: ' + name)
    with (folder / 'derived/device.csv').open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != manifest['rows']:
        raise ValueError('manifest row count mismatch')
    for row in rows:
        # Recheck original wire checksum, AFE PEC and quality semantics.
        parse_line(','.join(row[key] for key in FIELDS).encode('ascii'))
    return manifest, rows


def raw_stats(rows):
    values = [int(r['raw']) for r in rows if r['raw_valid'] == '1']
    return dict(records=len(rows), valid=len(values), invalid=len(rows)-len(values),
                mean=statistics.mean(values) if values else None,
                stddev=statistics.stdev(values) if len(values) > 1 else None,
                minimum=min(values) if values else None,
                maximum=max(values) if values else None,
                peak_to_peak=max(values)-min(values) if values else None)


def inspect_capture(folder):
    manifest, rows = load_capture(folder)
    channels = {}
    for channel in CHANNELS:
        selected = [r for r in rows if r['channel'] == channel]
        item = raw_stats(selected)
        # Aggregate variation includes drift and steps; it is not instrument accuracy.
        if channel in CELLS and item['mean'] is not None:
            item['nominal_voltage_mean_V'] = item['mean'] * 0.0001
            item['nominal_voltage_stddev_V'] = item['stddev'] * 0.0001 if item['stddev'] is not None else None
        channels[channel] = item
    return dict(schema='g01-raw-statistics-v1', source=str(Path(folder).resolve()),
                capture_manifest_sha256=sha(Path(folder)/'manifest.json'),
                evidence_scope=manifest['evidence_scope'], simulated=manifest['simulated'],
                rows=len(rows), channels=channels, calibration_verified=False,
                formal_G01_verdict=None,
                note='Standard deviation describes this capture, including drift; not accuracy or U95.')


def window_point(point, base, cache):
    channel = point['channel']
    if channel not in CELLS:
        raise ValueError('only cell voltage calibration is enabled')
    for key in ('id', 'boot_id', 'instrument_id', 'mapping_evidence',
                'reference_time_evidence', 'reference_condition'):
        if not isinstance(point.get(key), str) or not point[key].strip():
            raise ValueError('missing point evidence: ' + key)
    if point['role'] not in ('fit', 'validation'):
        raise ValueError('point role')
    first, last = point['seq_first'], point['seq_last']
    if type(first) is not int or type(last) is not int or not 0 <= first <= last <= 0xffffffff:
        raise ValueError('invalid sequence window; split at wrap')
    path = (base / point['capture']).resolve()
    if path not in cache:
        cache[path] = load_capture(path)
    manifest, rows = cache[path]
    selected = [r for r in rows if r['channel'] == channel and r['boot_id'] == point['boot_id']
                and first <= int(r['seq']) <= last]
    seqs = [int(r['seq']) for r in selected]
    if len(seqs) < 3 or len(seqs) != last-first+1 or seqs != list(range(first, last+1)):
        raise ValueError('point needs >=3 contiguous, unique, ordered samples')
    if any(r['raw_valid'] != '1' for r in selected):
        raise ValueError('invalid/stale sample in calibration window')
    for a, b in zip(selected, selected[1:]):
        elapsed = (int(b['end_ms'])-int(a['end_ms'])) & 0xffffffff
        if elapsed == 0 or elapsed > 1000:
            raise ValueError('time discontinuity in calibration window')
    ref = finite(point['reference_V'])
    if ref <= 0:
        raise ValueError('reference voltage must be positive')
    u95 = point.get('expanded_uncertainty_V')
    if u95 is not None:
        u95 = finite(u95)
        if u95 < 0 or not point.get('uncertainty_basis'):
            raise ValueError('U95 requires a nonnegative value and documented combined uncertainty basis')
    firmware = manifest.get('firmware_sha256')
    if not isinstance(firmware, str) or len(firmware) != 64 or any(c not in '0123456789abcdef' for c in firmware.lower()):
        raise ValueError('capture needs firmware identity')
    result = dict(point)
    result.update(capture=str(path), capture_manifest_sha256=sha(path/'manifest.json'),
                  source_data_sha256=manifest['sha256']['derived/device.csv'],
                  firmware_sha256=firmware, simulated=manifest['simulated'],
                  evidence_scope=manifest['evidence_scope'], reference_V=ref,
                  expanded_uncertainty_V=u95, raw=raw_stats(selected),
                  host_window_utc=[selected[0]['host_rx_utc'], selected[-1]['host_rx_utc']])
    return result


def assess(error, u95, tolerance):
    if u95 is None or tolerance is None:
        return None
    if abs(error)+u95 <= tolerance:
        return 'pass'
    if abs(error)-u95 > tolerance:
        return 'fail'
    return 'inconclusive'


def fit_plan(plan, base):
    if plan.get('schema') != 'g01-voltage-points-v1' or not plan.get('calibration_id'):
        raise ValueError('plan schema/calibration identity')
    cache = {}
    points = [window_point(p, base, cache) for p in plan['points']]
    if not points or len(set(p['id'] for p in points)) != len(points):
        raise ValueError('empty or duplicate point IDs')
    # Shared raw data is detected even if copied to a different folder.
    for i, p in enumerate(points):
        for q in points[:i]:
            if (p['source_data_sha256'], p['boot_id'], p['channel']) == (q['source_data_sha256'], q['boot_id'], q['channel']):
                if max(p['seq_first'], q['seq_first']) <= min(p['seq_last'], q['seq_last']):
                    raise ValueError('overlapping fit/validation or repeated point window')
    if len(set(p['firmware_sha256'] for p in points)) != 1:
        raise ValueError('mixed firmware identities')
    scopes = set((p['simulated'], p['evidence_scope']) for p in points)
    if len(scopes) != 1 or next(iter(scopes)) not in ((False, 'bench'), (True, 'simulation')):
        raise ValueError('mixed or inconsistent evidence scopes')
    tolerance = plan.get('tolerance_V')
    if tolerance is not None:
        tolerance = finite(tolerance)
        if tolerance <= 0 or not plan.get('acceptance_basis'):
            raise ValueError('positive tolerance and frozen acceptance basis required')
    models = {}
    for channel in CELLS:
        group = [p for p in points if p['channel'] == channel]
        if not group:
            continue
        fitting = [p for p in group if p['role'] == 'fit']
        validation = [p for p in group if p['role'] == 'validation']
        if len(set(p['reference_V'] for p in fitting)) < 3 or not validation:
            raise ValueError(channel + ': need >=3 distinct fit references and independent validation')
        if set(p['reference_condition'] for p in fitting) & set(p['reference_condition'] for p in validation):
            raise ValueError('validation cannot reuse fitting acquisition condition/window')
        x = [p['raw']['mean'] for p in fitting]
        y = [p['reference_V'] for p in fitting]
        xm, ym = statistics.mean(x), statistics.mean(y)
        denominator = sum((v-xm)**2 for v in x)
        if denominator == 0:
            raise ValueError('zero raw span')
        gain = sum((a-xm)*(b-ym) for a, b in zip(x, y))/denominator
        offset = ym-gain*xm
        if not math.isfinite(gain) or not math.isfinite(offset) or gain <= 0:
            raise ValueError('invalid/nonpositive voltage gain')
        errors = []
        for p in group:
            mean = p['raw']['mean']
            in_range = min(x) <= mean <= max(x)
            error = gain*mean+offset-p['reference_V']
            decision = assess(error, p['expanded_uncertainty_V'], tolerance)
            if p['role'] == 'fit' or not in_range or p['simulated']:
                decision = None
            errors.append(dict(point_id=p['id'], role=p['role'], in_fitted_raw_range=in_range,
                               predicted_V=gain*mean+offset, error_V=error,
                               output_stddev_V=abs(gain)*p['raw']['stddev'],
                               expanded_uncertainty_V=p['expanded_uncertainty_V'], verdict=decision))
        models[channel] = dict(model='voltage_V = gain_V_per_count * raw + offset_V',
                               gain_V_per_count=gain, offset_V=offset,
                               fitted_raw_range=[min(x), max(x)],
                               fitted_reference_range_V=[min(y), max(y)],
                               fit_point_ids=[p['id'] for p in fitting],
                               validation_point_ids=[p['id'] for p in validation], comparisons=errors)
    return dict(schema='g01-voltage-candidate-v1', calibration_id=plan['calibration_id'],
                evidence_scope=points[0]['evidence_scope'], simulated=points[0]['simulated'],
                tolerance_V=tolerance, acceptance_basis=plan.get('acceptance_basis'),
                models=models, points=points, firmware_changed=False,
                calibration_verified=False, formal_G01_verdict=None,
                note='Candidate only. Mapping/time evidence is operator supplied. No extrapolation or automatic deployment; review uncertainty and independent validation.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('inspect', 'fit'))
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.mode == 'inspect':
        report = inspect_capture(args.source)
    else:
        plan = json.loads(args.source.read_text(encoding='utf-8-sig'))
        report = fit_plan(plan, args.source.resolve().parent)
        report['point_plan_sha256'] = sha(args.source)
    report['tool_sha256'] = sha(__file__)
    with args.out.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, allow_nan=False)
    print(str(args.out.resolve()))


if __name__ == '__main__':
    main()
