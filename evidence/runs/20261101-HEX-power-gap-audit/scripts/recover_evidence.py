"""Reproduce focused STM32N647 HEX evidence. No device access or firmware writes.

Full binary/disassembly stay in local-only. Extracts are static evidence, not source.
"""
from pathlib import Path
import argparse, hashlib, json, re, struct, subprocess

def sha(data):
    return hashlib.sha256(data).hexdigest()

def parse_hex(path):
    memory = {}; upper = 0; entry = None; eof = False; records = 0
    for number, line in enumerate(path.read_text(encoding='ascii').splitlines(), 1):
        if not line.strip():
            continue
        if eof:
            raise ValueError(f'data after EOF at line {number}')
        if not line.startswith(':'):
            raise ValueError(f'not Intel HEX at line {number}')
        record = bytes.fromhex(line[1:]); records += 1
        if len(record) != record[0] + 5 or sum(record) % 256:
            raise ValueError(f'length/checksum at line {number}')
        offset = int.from_bytes(record[1:3], 'big')
        kind = record[3]; data = record[4:-1]
        if kind == 0:
            for i, value in enumerate(data):
                address = upper + offset + i
                if address in memory and memory[address] != value:
                    raise ValueError(f'inconsistent overlap at {address:x}')
                memory[address] = value
        elif kind == 1:
            if data: raise ValueError('invalid EOF')
            eof = True
        elif kind in (2, 4):
            if len(data) != 2: raise ValueError('invalid address record')
            upper = int.from_bytes(data, 'big') << (4 if kind == 2 else 16)
        elif kind == 5:
            if len(data) != 4: raise ValueError('invalid start address')
            entry = int.from_bytes(data, 'big')
        else:
            raise ValueError(f'unsupported record type {kind}')
    if not eof or not memory: raise ValueError('missing EOF or data')
    base = min(memory); end = max(memory) + 1
    if end-base > 4*1024*1024: raise ValueError('unexpected sparse size')
    return memory, base, end, entry, records

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--hex', required=True, type=Path)
    parser.add_argument('--objdump', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    source_hash = sha(args.hex.read_bytes())
    if source_hash != 'dd44fae11ed542ad6bcee45b35a13e93bd6632481b7d29662afda8ac7856be7f':
        raise ValueError('This address-specific recovery only applies to the recorded teacher HEX')
    mem, base, end, entry, records = parse_hex(args.hex)
    blob = bytes(mem.get(a, 255) for a in range(base, end))
    out = args.out.resolve(); local = out/'local-only'; local.mkdir(parents=True, exist_ok=True)
    binary = local/'prebuilt.bin'; binary.write_bytes(blob)
    command = [str(args.objdump), '-D', '-b', 'binary', '-m', 'armv8.1-m.main',
               '-M', 'force-thumb', '--adjust-vma='+hex(base), str(binary)]
    proc = subprocess.run(command, capture_output=True, check=True)
    (local/'disassembly-v81m.txt').write_bytes(proc.stdout)
    def words(address, count):
        return list(struct.unpack_from('<'+'I'*count, blob, address-base))
    expected = {
        'vector_head': (0x70100400, [0x34200000, 0x70102715]),
        'adc_irq_vector': (0x70100400+4*(16+46), [0x701025f1]),
        'adc1_default_channel_struct': (0x70101820, [11,6,3,0x3ff]),
        'adc1_active_channel_struct': (0x70105d00, [1,6,2,0x3ff]),
        'tim1_base_fields': (0x70101850, [0,0x20,1999,0]),
        'tim1_oc_fields': (0x70101860, [0x60,500,0,0]),
        'duty_multiplier_f32': (0x70101194, [0x44f9e000]),
        'current_lsb_f32': (0x701032e8, [0x39e674cd]),
    }
    checks = []
    for name,(address,want) in expected.items():
        got = words(address,len(want))
        if got != want: raise AssertionError((name,got,want))
        checks.append(dict(name=name,address=hex(address),words_hex=[hex(x) for x in got],pass_=True))
    (out/'byte-checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    ranges = {
        'adc-init-and-pins.txt': [(0x701015bc,0x701016f0),(0x70101800,0x70101840),(0x70101f6c,0x70102088)],
        'adc-runtime-and-shutdown.txt': [(0x701010bc,0x701011f4),(0x701025f0,0x7010260c),
            (0x70104ab0,0x70104d50),(0x70105bb8,0x70105dd0),(0x70106054,0x701060d4),
            (0x70106cf8,0x70106d60),(0x70107808,0x70107814),(0x701083f0,0x701085f8)],
        'pwm-config-and-hal.txt': [(0x7010171a,0x701017e0),(0x70101850,0x701018b0),
            (0x70102410,0x70102478),(0x70111cec,0x70111db0)],
        'pwm-start-stop-states.txt': [(0x70106cf8,0x70106e74),(0x70106fb0,0x70107030),
            (0x70107180,0x70107298),(0x7010741a,0x70107460),(0x70107628,0x70107792)],
    }
    disassembly = proc.stdout.decode('utf-8',errors='replace').splitlines()
    for name,sections in ranges.items():
        lines = ['Static reverse-engineering evidence. Literal pools are DATA, not instructions.',
                 'Source SHA256: '+source_hash, 'Decoder: armv8.1-m.main + force-thumb; MVE recognized.']
        for start,stop in sections:
            lines += ['', f'RANGE 0x{start:08x}..0x{stop:08x} (end exclusive)']
            for line in disassembly:
                match = re.match(r'([0-9a-f]{8}):',line)
                if not match or not start<=int(match[1],16)<stop: continue
                literal = re.search(r'@ \(?(0x[0-9a-f]+)\)?',line)
                if literal and '[pc,' in line:
                    address=int(literal[1],16); offset=address-base
                    if 0<=offset<=len(blob)-4:
                        value=words(address,1)[0]; line+=f' ; literal=0x{value:08x}'
                        if base<=value<end:
                            s=blob[value-base:value-base+160].split(b'\0')[0]
                            if s and all(32<=c<127 or c in (9,10,13) for c in s):
                                line+=' '+repr(s.decode('ascii'))
                        if 'vldr' in line:
                            fmt='<d' if re.search(r'vldr\S*\s+d',line) else '<f'
                            if offset+struct.calcsize(fmt)<=len(blob):
                                line+=' float='+repr(struct.unpack_from(fmt,blob,offset)[0])
                lines.append(line)
        (out/name).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    report=dict(source=str(args.hex.resolve()),sha256=source_hash,data_bytes=len(mem),span_bytes=len(blob),
        base=hex(base),end_exclusive=hex(end),entry=hex(entry),checksums_valid=True,eof=True,records=records,
        binary_sha256=sha(blob),objdump_command=command,
        objdump_version=subprocess.check_output([str(args.objdump),'--version']).decode().splitlines()[0],
        disassembly_sha256=sha(proc.stdout),address_specific_checks=len(checks),
        evidence_scope=['static'],bench_executed=False,firmware_changed=False,ghidra_executed=False)
    (out/'inventory.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'records_valid':records,'payload_bytes':len(mem),'byte_checks_passed':len(checks)},indent=2))

if __name__=='__main__': main()
