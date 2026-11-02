"""Read-only annotated excerpt of the independent firmware disassembly."""
from pathlib import Path
import re, struct, sys

OLD = Path(__file__).resolve().parents[1] / 'local-only'
blob = (OLD / 'prebuilt.bin').read_bytes()
BASE = 0x70100400
start, end = (int(x, 16) for x in sys.argv[1:3])
for line in (OLD / 'disassembly-v81m.txt').read_text().splitlines():
    m = re.match(r'([0-9a-f]{8}):', line)
    if not m or not start <= int(m[1], 16) < end:
        continue
    literal = re.search(r'@ \(?(0x[0-9a-f]+)\)?', line)
    if literal and ('[pc,' in line):
        addr = int(literal[1], 16)
        off = addr-BASE
        if 0 <= off <= len(blob)-4:
            word = struct.unpack_from('<I', blob, off)[0]
            line += f' ; literal=0x{word:08x}'
            if BASE <= word < BASE + len(blob):
                text = blob[word-BASE:word-BASE+160].split(b'\0')[0]
                if text and all(32 <= c < 127 or c in (10, 13, 9) for c in text):
                    line += ' ' + repr(text.decode('ascii'))
            if line.find('vldr') >= 0:
                fmt = '<d' if re.search(r'vldr\S*\s+d', line) else '<f'
                if off+struct.calcsize(fmt) <= len(blob):
                    line += ' float=' + repr(struct.unpack_from(fmt, blob, off)[0])
    print(line)
