"""Offline audit of a disabled ADC mux run; never opens a serial port."""
import argparse, csv, hashlib, json, statistics, sys
from pathlib import Path


def analyze(run, root, out):
    sys.path.insert(0, str(root/'scripts/g03'))
    from adc_diagnostics import parse as parse_adc
    from relay_capture import parse as parse_relay
    r = json.loads((run/'result.json').read_text())
    if not (r.get('restored') and r.get('adc_status_restored') and r.get('relay_record_preserved')):
        raise ValueError('Incomplete register or board-state restoration')
    for name, expected in r['sha256'].items():
        if hashlib.sha256((run/name).read_bytes()).hexdigest() != expected:
            raise ValueError('Raw artifact hash mismatch: '+name)
    actual_ops = []
    for path in sorted(run.glob('*/events.jsonl')):
        for line in path.read_text().splitlines():
            event = json.loads(line)
            if 'tx_hex' not in event:
                continue
            wire = bytes.fromhex(event['tx_hex'])
            body = wire.split(b'*')[0].decode().split(',')
            op, arg = int(body[-2]), int(body[-1])
            if op not in (20, 21, 30) or arg:
                raise ValueError('Unexpected command in disabled-only run')
            actual_ops.append(op)
    if actual_ops.count(21) != 7:
        raise ValueError('Expected seven independent diagnostic requests')
    rows, summary = [], []
    measurements = [(x['label'], x['channel'], x['sampling_code'], x['diagnostic']) for x in r['measurements']]
    measurements.append(('restored-current',1,3,r['restored_current']['diagnostic']))
    for label, channel, sample_code, d in measurements:
        matching = []
        for line in (run/label/'serial.bin').read_bytes().splitlines():
            if line.startswith(b'#G3D,'):
                decoded = parse_adc(line)
                if decoded['id'] == d['id']:
                    matching.append(decoded)
        if matching != [d]:
            raise ValueError('Diagnostic raw/JSON mismatch: '+label)
        if d['count'] != 64 or d['sqr1'] >> 6 & 31 != channel or d['pcsel'] != 1 << channel:
            raise ValueError('Channel identity/count mismatch')
        if d['difsel'] or d['gcomp'] or d['ofr1']:
            raise ValueError('Unexpected analog data transformation')
        values, tail = d['samples'], d['samples'][16:]
        summary.append(dict(label=label,channel=channel,sampling_cycles={3:11.5,7:1499.5}[sample_code],
                            count=64,first=values[0],minimum=min(values),maximum=max(values),
                            median=statistics.median(values),tail_median=statistics.median(tail),
                            tail_min=min(tail),tail_max=max(tail),tail_p2p=max(tail)-min(tail)))
        for index, raw in enumerate(values):
            rows.append(dict(label=label,channel=channel,request_id=d['id'],sample_index=index,
                             raw=raw,startup_observation=int(index<16),physical_valid=0))
    for label, key in [('relay-before','relay_before'),('relay-after','relay_after')]:
        status = r[key]['status']
        matches = [parse_relay(line) for line in (run/label/'serial.bin').read_bytes().splitlines() if line.startswith(b'#G3R,')]
        if status not in matches or status['actual_bits'] or status['live_used'] != 1:
            raise ValueError('Relay status mismatch')
    result = dict(evidence_scope=['bench'],status='complete',verdict='inconclusive',
                  disabled_mux_acquisition='pass',root_cause_confirmed=False,
                  count=len(rows),groups=summary,commands=actual_ops,physical_valid=0,
                  no_power_start_command=True,restored=True,relay_record_preserved=True,
                  note='Static raw input comparison. No per-sample hardware timestamp in diagnostic schema. Tail excludes first 16 only for description; all raw values retained.')
    out.mkdir(exist_ok=False)
    for filename, values in [('samples.csv',rows),('summary.csv',summary)]:
        with (out/filename).open('x',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    (out/'analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(analyze(args.run,args.root,args.out),indent=2))
