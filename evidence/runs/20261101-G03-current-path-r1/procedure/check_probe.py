import ast, runpy
from pathlib import Path
p = Path(__file__).with_name('probe_current_path.py')
ast.parse(p.read_text())
m = runpy.run_path(str(p))
SQR, S1, S2, PC, CCR = [m[k] for k in ('SQR', 'SMPR1', 'SMPR2', 'PCSEL', 'CCR')]
original = {SQR: 0xabcdef40, S1: 0x12345678, S2: 0x87654321, PC: 2, CCR: 0x12345678}
for ch in (0, 1, 11, 14, 17):
    for sample in (3, 7):
        v = m['mux_settings'](original, ch, sample)
        assert v[SQR] & 15 == 0 and (v[SQR] >> 6) & 31 == ch
        assert v[SQR] & ~0x7cf == original[SQR] & ~0x7cf
        assert v[PC] == 1 << ch
        address, shift = (S1, ch * 3) if ch < 10 else (S2, (ch - 10) * 3)
        assert v[address] >> shift & 7 == sample
        assert (v[address] ^ original[address]) & ~(7 << shift) == 0
        assert v[S2 if address == S1 else S1] == original[S2 if address == S1 else S1]
        assert v[CCR] == original[CCR] | ((1 << 22) if ch == 17 else 0)
for bad in (-1, 2, 10, 18, 31, 32):
    try:
        m['mux_settings'](original, bad, 7)
    except ValueError:
        pass
    else:
        raise AssertionError('Unreviewed channel accepted')
assert original[SQR] == 0xabcdef40
print('PASS: register mask preservation, allowed channels, VREF bit, no mutation')
