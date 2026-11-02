"""Host checks of production G02 state/port code; no hardware access."""
import argparse
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--cc', default='gcc')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    bsp = root / 'BMS_EXv1.1/BMS_EX/BSP'
    test = root / 'tests/g02'
    results = []

    def run(name, command):
        command = [str(x) for x in command]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        results.append(dict(name=name, command=command, exit_code=result.returncode))
        (out / 'checks.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        if result.returncode:
            raise RuntimeError(name + ' failed; see preserved output')

    run('compiler', [args.cc, '--version'])
    flags = [args.cc, '-std=c99', '-Wall', '-Wextra', '-Werror', '-pedantic']
    run('build-control', flags + ['-I' + str(bsp), test / 'test_control.c',
                                 bsp / 'g02_control.c', '-o', out / 'control.exe'])
    run('control', [out / 'control.exe'])
    for variant in ('default', 'pins-simulated'):
        extra = ['-DG02_ALLOW_PIN_OUTPUT=1'] if variant == 'pins-simulated' else []
        run('build-' + variant, flags + extra + ['-I' + str(test / 'stubs'),
            '-I' + str(bsp), test / 'test_port.c', bsp / 'g02_control.c',
            bsp / 'g02_port.c', root / 'tests/g03/relay_bridge_stub.c', bsp / 'g03_control.c', bsp / 'g03_port.c', root / 'tests/g03/adc_bridge_stub.c', '-o', out / (variant + '.exe')])
        run(variant, [out / (variant + '.exe')])

    run('build-link', flags + ['-I' + str(test / 'stubs'), '-I' + str(bsp),
        test / 'test_link.c', bsp / 'g02_control.c', bsp / 'g02_port.c', root / 'tests/g03/relay_bridge_stub.c',
        bsp / 'g02_link.c', bsp / 'g03_control.c', bsp / 'g03_port.c', root / 'tests/g03/adc_bridge_stub.c', '-o', out / 'link.exe'])
    run('link', [out / 'link.exe'])
    host_path = root / 'scripts/g02/host_diagnostics.py'
    spec = importlib.util.spec_from_file_location('g02_host', str(host_path))
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    replies = [x for x in (out / 'link.stdout').read_bytes().splitlines() if x.startswith(b'#G02,')]
    assert replies and all(host.parse(x)['pins_gate'] == 0 for x in replies)
    run('host-python', [sys.executable, '-m', 'unittest', 'discover', '-s', test,
                       '-p', 'test_host.py', '-v'])

    project = root / 'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/BMS_EX_Appli.uvprojx'
    targets = ET.parse(str(project)).findall('./Targets/Target')
    assert len(targets) == 2
    for target in targets:
        files = [x.text for x in target.findall('.//FileName')]
        assert files.count('g02_control.c') == files.count('g02_port.c') == files.count('g02_link.c') == 1
        defines = ' '.join(x.text or '' for x in target.findall('.//Define'))
        assert 'G02_ALLOW_PIN_OUTPUT=1' not in defines
    main_source = (root / 'BMS_EXv1.1/BMS_EX/Appli/Core/Src/main.c').read_text(encoding='utf-8-sig')
    assert 'G02_PortInit();' in main_source and 'G02_Task();' in main_source
    assert 'if (G02_MeasurementAllowed()) Measurement_Task();' in main_source
    assert 'G02_Start(' not in main_source
    assert 'sConfigOC.Pulse = G02_INITIAL_COMPARE;' in main_source
    assert '  PeriphCommonClock_Config();' in main_source
    it = (root / 'BMS_EXv1.1/BMS_EX/Appli/Core/Src/stm32n6xx_it.c').read_text(encoding='utf-8-sig')
    assert it.count('G02_CPUFault();') == 6
    assert 'if (!G02_ADC_IRQHandler()) HAL_ADC_IRQHandler(&hadc1);' in it
    sources = list(bsp.glob('g02_*.[ch]')) + list(test.glob('*.c')) + list(test.glob('*.py')) + [test / 'stubs/main.h'] + list((root / 'scripts/g02').glob('*.py'))
    report = dict(scope=['static', 'simulation'], verdict=None, checks='passed',
        hardware_verified=False, pin_output_run='host simulation only',
        limitations=['Register/HAL stubs do not model electrical behavior, actual clock/ADC timing or reset pin levels.',
                     'Native tests and build are not G02 bench acceptance.'],
        sha256={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (out / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('PASS: production G02 core + port + UART link and host parser; hardware unverified.')


if __name__ == '__main__':
    main()
