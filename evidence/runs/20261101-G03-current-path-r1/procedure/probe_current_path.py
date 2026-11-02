"""Disabled, temporary ADC1 mux investigation on the identified relay-r2 image.

No flash/reset/power-start operation. Saves/restores exact mux/sample registers.
Regular telemetry while mux is overridden is intentionally excluded.
"""
from pathlib import Path
import datetime, hashlib, json, re, statistics, subprocess, sys

ROOT = Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
RUN = ROOT / 'evidence/runs/20261101-G03-current-path-r1'
CLI = r'E:\ST\STM32CubeIDE_1.19.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.200.202503041107\tools\bin\STM32_Programmer_CLI.exe'
CONN = [CLI, '-c', 'port=SWD', 'sn=16004A002933353739303541', 'freq=100', 'mode=HOTPLUG']
FW = '8ff78e03997c4a5facd8f6feade09024fdd4721a3f0e32fc3531312bf1598c49'
SQR, SMPR1, SMPR2, PCSEL, CCR = 0x50022030, 0x50022014, 0x50022018, 0x5002201c, 0x50022308
WRITABLE = (SQR, SMPR1, SMPR2, PCSEL, CCR)
CR = 0x50022008
sys.path.insert(0, str(ROOT / 'scripts/g03'))
from adc_diagnostics import Session as ADCSession, ok
from relay_capture import Session as RelaySession
import serial


def mux_settings(saved, channel, sampling_code):
    if channel not in (0, 1, 11, 14, 17) or sampling_code not in (3, 7):
        raise ValueError('Only reviewed input channels and sampling modes')
    result = dict(saved)
    result[SQR] = (saved[SQR] & ~((31 << 6) | 15)) | channel << 6
    result[PCSEL] = 1 << channel
    address = SMPR1 if channel < 10 else SMPR2
    shift = 3 * (channel if channel < 10 else channel - 10)
    result[address] = (saved[address] & ~(7 << shift)) | sampling_code << shift
    if channel == 17:
        result[CCR] |= 1 << 22
    return result


class Probe:
    def __init__(self, out):
        self.out = out
        self.index = 0
        self.commands = []
        self.counter = 0

    def command(self, name, args):
        self.index += 1
        stem = self.out / 'swd' / ('%03d-' % self.index + name)
        record = dict(name=name, command=CONN + args)
        self.commands.append(record)
        try:
            r = subprocess.run(CONN + args, capture_output=True, timeout=25)
            record['exit_code'] = r.returncode
            stem.with_suffix('.stdout').write_bytes(r.stdout)
            stem.with_suffix('.stderr').write_bytes(r.stderr)
            text = r.stdout.decode(errors='replace')
            if r.returncode or 'Error:' in text:
                raise RuntimeError(name + ': ' + text[-900:])
            return text
        finally:
            (self.out / 'swd/commands.json').write_text(json.dumps(self.commands, indent=2))

    def read(self, name, address):
        text = self.command(name, ['-r32', hex(address), '4'])
        match = re.search('0x%08X' % address + r'\s*:\s*([0-9A-F]{8})', text, re.I)
        if not match:
            raise RuntimeError('No register in readback: ' + text)
        return int(match[1], 16)

    def halt_disabled(self, name):
        # Read-only retries let an interrupted regular conversion finish.
        # No register write is permitted until ADC1 is disabled and idle.
        for attempt in range(3):
            tag = name + '-%d' % attempt
            self.command(tag + '-halt', ['-halt'])
            cr = self.read(tag + '-cr', CR)
            if not cr & 0xc000003f:
                return
            self.command(tag + '-busy-resume', ['-run'])
        raise RuntimeError('ADC not disabled and idle at halt: ' + hex(cr))

    def apply(self, name, settings):
        if set(settings) != set(WRITABLE):
            raise ValueError('Register write allowlist')
        for address, value in settings.items():
            self.command(name + '-write-%x' % address, ['-w32', hex(address), hex(value)])
            if self.read(name + '-verify-%x' % address, address) != value:
                raise RuntimeError('Register verify failed')

    def uart(self, name, relay=False, diagnostic=False):
        folder = self.out / name
        folder.mkdir(exist_ok=False)
        link = serial.Serial()
        link.port = 'COM11'
        link.baudrate = 115200
        link.timeout = .05
        link.write_timeout = 1
        link.dtr = link.rts = False
        s = (RelaySession if relay else ADCSession)(link, folder)
        s.counter = max(s.counter, self.counter)
        try:
            link.open()
            status = ok(s.request(30 if relay else 20, timeout=8))
            s.identified = True
            if status['actual_bits'] or status['faults']:
                raise RuntimeError('Require disabled, fault-free board: ' + str(status))
            if relay:
                if (status['firmware'], status['state'], status['live_used']) != ('g03-relay-r2', 5, 1):
                    raise RuntimeError('Require preserved third relay result: ' + str(status))
            else:
                if any(status[k] for k in ('state', 'owns_adc', 'configured', 'profile', 'selfcal')):
                    raise RuntimeError('Require untouched idle profile 0: ' + str(status))
            result = dict(status=status)
            if diagnostic:
                result['diagnostic'] = ok(s.request(21, 0, timeout=8))
                result['after'] = ok(s.request(20, timeout=8))
                if result['diagnostic']['count'] != 64 or result['after']['owns_adc']:
                    raise RuntimeError('Incomplete diagnostic/cleanup')
            (folder / 'result.json').write_text(json.dumps(result, indent=2))
            return result
        finally:
            self.counter = s.counter
            s.close() if relay else s.finish()


def main():
    identity = json.loads((ROOT / 'evidence/runs/20261101-G03-relay-r2/production-source-manifest.json').read_text())
    for entry in identity['files']:
        if hashlib.sha256((ROOT / entry['path']).read_bytes()).hexdigest() != entry['sha256']:
            raise RuntimeError('Source changed since verified image: ' + entry['path'])
    image = identity['firmware']['BMS_EX_Release']
    if hashlib.sha256((ROOT / image['path']).read_bytes()).hexdigest() != FW:
        raise RuntimeError('Release image hash mismatch')
    RUN.mkdir(exist_ok=False)
    (RUN / 'swd').mkdir()
    (RUN / 'procedure').mkdir()
    (RUN / 'procedure/probe_current_path.py').write_bytes(Path(__file__).read_bytes())
    plan = [(1, 3, 'current-before'), (0, 7, 'input-0'), (11, 7, 'input-11'),
            (14, 7, 'input-14'), (17, 7, 'internal-vref'), (1, 7, 'current-long')]
    manifest = dict(run_id=RUN.name, firmware='g03-relay-r2', firmware_sha256=FW,
                    created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    evidence_scope=['bench'], mode='disabled_adc_mux_diagnostic',
                    plan=plan, profile=0, physical_valid=0, power_start_commands=[],
                    no_reset=True, no_flash=True, no_calibration_change=True,
                    regular_telemetry_during_override_excluded=True,
                    caveat='Static mux comparison cannot prove external current transfer or wiring continuity')
    (RUN / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    p = Probe(RUN)
    saved = {}
    changed = False
    result = dict(verdict=None, measurements=[], restored=False)
    try:
        result['relay_before'] = p.uart('relay-before', relay=True)
        result['adc_before'] = p.uart('adc-before')
        print('Confirmed relay-r2 DONE, live_used=1, outputs=0; beginning disabled mux probe', flush=True)
        p.halt_disabled('initial')
        for address in WRITABLE:
            saved[address] = p.read('saved-%x' % address, address)
        result['saved'] = saved
        result['adc_or'] = p.read('adc-option', 0x500220d0)
        if saved[SQR] != 64 or saved[PCSEL] != 2 or (saved[SMPR1] >> 3) & 7 != 3:
            raise RuntimeError('Unexpected original ADC1 channel/sample settings')
        (RUN / 'saved-registers.json').write_text(json.dumps(saved, indent=2))
        for index, (channel, sample_code, label) in enumerate(plan):
            if index:
                p.halt_disabled(label)
            settings = mux_settings(saved, channel, sample_code)
            changed = True
            p.apply(label, settings)
            p.command(label + '-run', ['-run'])
            d = p.uart(label, diagnostic=True)['diagnostic']
            if (d['sqr1'], d['pcsel'], d['smpr1'], d['common_ccr']) != tuple(settings[a] for a in (SQR, PCSEL, SMPR1, CCR)):
                raise RuntimeError('Firmware altered diagnostic channel/sample configuration')
            row = dict(label=label, channel=channel, sampling_code=sample_code, settings=settings,
                       diagnostic=d, median=statistics.median(d['samples']),
                       tail_median=statistics.median(d['samples'][16:]),
                       tail_min=min(d['samples'][16:]), tail_max=max(d['samples'][16:]))
            result['measurements'].append(row)
            (RUN / 'progress.json').write_text(json.dumps(result, indent=2))
            print(json.dumps({k: row[k] for k in ('label', 'channel', 'median', 'tail_median', 'tail_min', 'tail_max')}), flush=True)
        result['verdict'] = 'pass_disabled_diagnostic_only'
    except Exception as error:
        result['error'] = repr(error)
        result['verdict'] = 'failed_or_unavailable'
        print('Probe stopped: ' + repr(error), flush=True)
    finally:
        try:
            if changed:
                p.halt_disabled('restore')
                p.apply('restore', saved)
                result['restored'] = True
            p.command('final-run', ['-run'])
            result['restored_current'] = p.uart('restored-current', diagnostic=True)
            result['relay_after'] = p.uart('relay-after', relay=True)
            before = result['adc_before']['status']
            after = result['restored_current']['after']
            for key in ('cfgr1', 'cfgr2', 'calfact', 'selfcal', 'profile', 'actual_bits'):
                if before[key] != after[key]:
                    raise RuntimeError('ADC state not restored: ' + key)
            result['adc_status_restored'] = True
            for key in ('state', 'live_used', 'written', 'on_cycles', 'off_cycles', 'actual_bits'):
                if result['relay_before']['status'][key] != result['relay_after']['status'][key]:
                    raise RuntimeError('Relay result changed: ' + key)
            result['relay_record_preserved'] = True
        except Exception as error:
            result['restore_error'] = repr(error)
            result['verdict'] = 'failed_or_unavailable'
            print('Restore/check issue: ' + repr(error), flush=True)
        result['sha256'] = {str(x.relative_to(RUN)): hashlib.sha256(x.read_bytes()).hexdigest()
                            for x in RUN.rglob('*') if x.is_file()}
        (RUN / 'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps({k: v for k, v in result.items() if k in ('verdict', 'restored', 'adc_status_restored', 'relay_record_preserved', 'error', 'restore_error')}), flush=True)
    return 0 if result['verdict'] == 'pass_disabled_diagnostic_only' else 1


if __name__ == '__main__':
    raise SystemExit(main())
