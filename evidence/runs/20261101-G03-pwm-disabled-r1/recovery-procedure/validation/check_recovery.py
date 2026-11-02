"""Import/schema/default-plan smoke checks only; serial import is forbidden."""
import ast, binascii, builtins, hashlib, importlib.util, json
from pathlib import Path
import subprocess, sys

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / 'post_pwm_recovery.py'
OUT = Path(__file__).resolve().parent
ast.parse(SOURCE.read_text(encoding='utf-8'))
original_import = builtins.__import__
def forbid_serial(name, *args, **kwargs):
    if name == 'serial' or name.startswith('serial.'):
        raise RuntimeError('Serial import attempted in offline validation')
    return original_import(name, *args, **kwargs)
builtins.__import__ = forbid_serial
spec = importlib.util.spec_from_file_location('recovery', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
def wire(kind, fields, label=m.FIRMWARE):
    body = (kind + ',' + label + ',' + ','.join(map(str, fields))).encode()
    return body + b'*%04X\n' % binascii.crc_hqx(body, 65535)
def reject(callback):
    try: callback()
    except ValueError: return
    raise AssertionError('Invalid data accepted')
g02 = [0] * len(m.g02.FIELDS)
g02[0] = 1
assert m.parse_report(wire('#G02', g02))['firmware'] == m.FIRMWARE
reject(lambda: m.parse_report(wire('#G02', g02, 'g03-relay-r2')))
g02[-1] = 1
reject(lambda: m.parse_report(wire('#G02', g02)))
relay = [0] * len(m.relay.STATUS)
relay[0] = 2
assert m.parse_report(wire('#G3R', relay))['actual_bits'] == 0
relay[13] = 16
reject(lambda: m.parse_report(wire('#G3R', relay)))
relay[13] = 0
relay[18] = 1
reject(lambda: m.parse_report(wire('#G3R', relay)))
assert not ({32, 41, 49} & m.ALLOWED)
assert m.summarize_g01([])['verdict'] == 'fail'
row = dict(channel='current_mcu_adc1', seq='1', start_ms='0', end_ms='1', age_ms='0',
           raw='', raw_valid='0')
summary = m.summarize_g01([row])
assert summary['channels']['current_mcu_adc1']['raw_min'] is None
assert summary['channels']['current_mcu_adc1']['invalid'] == 1
# In-process default invocation has a hard import guard, proving plan reaches
# no pyserial import. Child default invocation supplies its exact JSON artifact.
sys.argv = [str(SOURCE)]
assert m.main() == 0
result = subprocess.run([sys.executable, str(SOURCE)], capture_output=True)
assert result.returncode == 0
plan = json.loads(result.stdout)
assert plan['mode'] == 'plan' and not plan['serial_opened']
(OUT / 'default-plan.json').write_bytes(result.stdout)
validation = dict(verdict='pass', hardware_access=False, serial_import_forbidden=True,
                  scope='AST/import, identity/schema/closed-output guards, empty-invalid G01, default plan only',
                  production_sequence_executed=False,
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest())
(OUT / 'validation.json').write_text(json.dumps(validation, indent=2), encoding='utf-8')
print(json.dumps(validation, indent=2))
