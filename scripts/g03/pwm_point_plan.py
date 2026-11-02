"""Offline PWM timing/CCR plan and evidence gaps. No serial or GPIO interface."""
import argparse,hashlib,json,re
from fractions import Fraction
from pathlib import Path

def deadtime_ticks(dtg):
    if type(dtg) is not int or not 0<=dtg<=255:raise ValueError('8-bit DTG required')
    if dtg<128:return dtg
    if dtg<192:return (64+(dtg&63))*2
    if dtg<224:return (32+(dtg&31))*8
    return (32+(dtg&31))*16

def deadtime_code(request_ns,timer_hz,ckd=1):
    if type(timer_hz) is not int or timer_hz<=0 or ckd not in (1,2,4):raise ValueError('Clock/CKD')
    requested=Fraction(str(request_ns))
    if requested<0:raise ValueError('Negative deadtime')
    # Choose the smallest representable interval >= the request; never round down.
    for dtg in range(256):
        ns=Fraction(deadtime_ticks(dtg)*ckd*1000000000,timer_hz)
        if ns>=requested:return dict(dtg=dtg,requested_ns=float(requested),represented_ns=float(ns),ckd=ckd,timer_hz=timer_hz)
    raise ValueError('Deadtime exceeds DTG range; no clamp or wrap to zero')

def fixed_point(duty,arr=2000,timer_hz=400000000,psc=0):
    d=Fraction(str(duty))
    if not 0<d<1 or type(arr) is not int or not 2<=arr<=65535:raise ValueError('Duty/ARR')
    if type(timer_hz) is not int or timer_hz<=0 or type(psc) is not int or not 0<=psc<=65535:raise ValueError('Clock/PSC')
    quantized=d*arr;ccr=(quantized.numerator*2+quantized.denominator)//(2*quantized.denominator)
    if not 0<ccr<arr:raise ValueError('Quantization reaches a rail')
    return dict(requested_duty=float(d),ccr=ccr,arr=arr,actual_timer_duty=float(Fraction(ccr,arr)),center_aligned_frequency_Hz=float(Fraction(timer_hz,2*(psc+1)*arr)),upper_switch_mapping_verified=False)

def assess(root,comparison):
    root=Path(root);bsp=root/'BMS_EXv1.1/BMS_EX/BSP';main=root/'BMS_EXv1.1/BMS_EX/Appli/Core/Src/main.c'
    hp_path=root/'instructions/specs/hardware-profile.json';hp=json.loads(hp_path.read_text(encoding='utf-8'))
    src=main.read_text(encoding='utf-8');matches=re.findall(r'sBreakDeadTimeConfig\.(\w+)\s*=\s*([^;]+);',src)
    settings=dict(matches);gaps=[]
    if settings.get('DeadTime')=='0':gaps.append('Current TIM1 programmed deadtime is zero; physical driver/MOS turn-off overlap has no board evidence')
    if settings.get('BreakState')=='TIM_BREAK_DISABLE':gaps.append('TIM1 Break is disabled; no verified hardware fault source/polarity/routing')
    for key in ['permitted_test_duty_min','permitted_test_duty_max','effective_deadtime_min_ns','stop_delay_limit_us','open_loop_point_max_ms']:
        if hp['control'].get(key) is None:gaps.append('Missing physical/control bound: control.'+key)
    for key in ['converter_current_max_A','converter_voltage_max_V','supply_current_limit_A']:
        if hp['limits'].get(key) is None:gaps.append('Missing energy/limit evidence: limits.'+key)
    deltas=[r['channels']['mcu_current']['delta_median'] for r in comparison['runs']]
    afe=[r['channels']['afe_current']['delta_median'] for r in comparison['runs']]
    gaps.append('MCU ADC1/PA1 response path is not verified; see observed AFE versus MCU deltas, not a calibrated fast protection signal')
    gaps.append('PA9/PF7 to high/low gate driver mapping and effective deadtime require board-specific evidence')
    gaps.append('Existing g03_adc_port.c is explicitly output-disabled; a reviewed real PWM execution/protection adapter is still required')
    paths=[main,bsp/'g02_port.h',bsp/'g03_adc_port.c',hp_path,root/'BMS_EXv1.1/BMS_EX/Drivers/STM32N6xx_HAL_Driver/Inc/stm32n6xx_ll_tim.h']
    return dict(scope='static/offline preparation; no board PWM operation',power_ready=False,firmware_changed=False,firmware_timing=settings,course_points_only=[fixed_point(d) for d in ['0.90','0.80','0.70','0.60','0.50','0.40']],candidate_start_duty=None,candidate_deadtime_ns=None,fast_feedback_observation=dict(afe_delta_codes=afe,mcu_delta_codes=deltas,physical_valid=0),gaps=gaps,source_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},notes=['33 ohm load and a short command window do not bound internal half-bridge shoot-through current','DTG calculator follows the bundled ST LL_TIM four-range encoding and rounds upward; it does not choose a board-safe deadtime','No loop, serial write, reset, or power enable is implemented by this tool'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--comparison',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    result=assess(a.root,json.loads(Path(a.comparison).read_text(encoding='utf-8')))
    with Path(a.out).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(power_ready=False,gap_count=len(result['gaps']),mcu_delta_codes=result['fast_feedback_observation']['mcu_delta_codes'])))
if __name__=='__main__':main()
