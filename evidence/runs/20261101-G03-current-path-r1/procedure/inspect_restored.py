import json, runpy
from pathlib import Path
m = runpy.run_path(str(Path(__file__).with_name('probe_current_path.py')))
out = m['RUN'] / 'restored-register-inspect'
out.mkdir(exist_ok=False)
(out/'swd').mkdir()
p = m['Probe'](out)
values = {}
for name, address in [('pwr_svmcr3',0x5602483c),('gpioa_moder',0x56020000),
                      ('gpioa_pupdr',0x5602000c),('tim1_cr1',0x52000000),
                      ('tim1_ccer',0x52000020),('tim1_bdtr',0x52000044),
                      ('gpiob_odr',0x56020414),('gpiog_odr',0x56021814)]:
    values[name] = p.read(name,address)
values['analog_supply_valid'] = bool(values['pwr_svmcr3'] & (1<<12))
values['input_modes'] = {str(pin): (values['gpioa_moder'] >> (2*pin)) & 3 for pin in (0,1,2,10)}
values['input_pulls'] = {str(pin): (values['gpioa_pupdr'] >> (2*pin)) & 3 for pin in (0,1,2,10)}
values['outputs_disabled'] = not (values['tim1_cr1']&1 or values['tim1_ccer'] or
    values['tim1_bdtr']&(1<<15) or values['gpiob_odr']&(1<<5) or values['gpiog_odr']&(1<<5))
values['mode'] = 'SWD HOTPLUG read-only; no halt, reset or register write'
(out/'result.json').write_text(json.dumps(values,indent=2))
(m['RUN']/'procedure/inspect_restored.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps(values,indent=2))
assert values['outputs_disabled']
