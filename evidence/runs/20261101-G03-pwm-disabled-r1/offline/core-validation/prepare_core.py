from pathlib import Path

ROOT = Path(r'D:\ADMIN\Desktop\WEIJI\zonghe')
WORK = Path(__file__).parents[1] / 'workspace'
SOURCE = ROOT / 'evidence/runs/20261101-HEX-baseline-followup/candidate'
BSP = WORK / 'BMS_EXv1.1/BMS_EX/BSP'
TEST = WORK / 'tests/g03'
TEST.mkdir(parents=True, exist_ok=True)
for name in ('pwm_oneshot.c', 'pwm_oneshot.h', 'test_pwm_oneshot.c'):
    text = (SOURCE / name).read_text(encoding='utf-8').replace('_ms', '_us')
    text = text.replace('millisecond', 'microsecond')
    if name == 'pwm_oneshot.h':
        text = text.replace('/* OFFLINE CANDIDATE, not teacher source and not a board power firmware.',
                            '/* HAL-independent one-shot core, derived from the r2 offline candidate.\n * Time values are uint32 microseconds supplied by one free-running hardware\n * counter. The current adapter is output-disabled; this core alone grants no\n * permission to run a physical power stage.')
        text = text.replace('It must keep advancing while foreground/low-priority IRQs stall.',
                            'It must keep advancing while foreground/low-priority IRQs stall.\n     * Use a free-running 1 MHz timer; not SysTick and not DWT/ticks-per-us.\n     * Each interval and any unchecked elapsed time must stay below 2^31 us.\n     * A periodic deadline includes IRQ spacing/latency; run_us is a decision\n     * threshold, not a proven maximum electrical on-time.')
    target = (TEST if name.startswith('test_') else BSP) / name
    if target.exists():
        raise RuntimeError('Refusing to overwrite existing new integration file: '+str(target))
    target.write_text(text, encoding='utf-8')
print('Copied r2 core and tests with microsecond time API')
