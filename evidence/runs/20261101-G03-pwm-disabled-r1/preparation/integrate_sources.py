from pathlib import Path
ROOT=Path(__file__).parent/'workspace/BMS_EXv1.1/BMS_EX'
def edit(name, changes):
    p=ROOT/name;s=p.read_text(encoding='utf-8')
    for old,new in changes:
        if old not in s:raise RuntimeError('Missing anchor in '+name+': '+old[:90])
        s=s.replace(old,new)
    p.write_text(s,encoding='utf-8',newline='\n')
for name in ('BSP/g02_port.c','BSP/g02_link.c','BSP/g03_port.c','BSP/g03_adc_port.c','BSP/g03_relay_port.c'):
    edit(name,[('#include "g03_relay_port.h"','#include "g03_relay_port.h"\n#include "g03_pwm_port.h"\n#include "firmware_identity.h"')])
for name in ('BSP/g02_link.c','BSP/g03_port.c','BSP/g03_adc_port.c'):
    edit(name,[('g03-relay-r2,','" BMS_DIAG_FIRMWARE ",')])
edit('BSP/g03_relay_profile.h',[
 ('#define G03_RELAY_PROFILE_H','#define G03_RELAY_PROFILE_H\n#include "firmware_identity.h"'),
 ('#define G3R_FIRMWARE "g03-relay-r2"','#define G3R_FIRMWARE BMS_DIAG_FIRMWARE')])
edit('BSP/measurement.c',[
 ('#include "measurement.h"','#include "measurement.h"\n#include "firmware_identity.h"'),
 ('fw=g03-relay-r2,','fw=" BMS_DIAG_FIRMWARE ",'),
 ('profile=cnn647b-g03-relay-r2,','profile=cnn647b-" BMS_DIAG_FIRMWARE ",'),
 ('#BOOT,g03-relay-r2,','#BOOT," BMS_DIAG_FIRMWARE ",')])
edit('BSP/g02_port.c',[
 ('    G03_RelayCPUFault();','    G02_EmergencyOff();\n    G03_PWM_CPUFault();\n    G03_RelayCPUFault();'),
 ('return !G03_RelayBusy()','return !G03_PWM_Owns() && !G03_RelayBusy()'),
 ('case G02_CMD_STOP: G03_RelayStop();','case G02_CMD_STOP: G03_PWM_Stop(); G03_RelayStop();'),
 ('case G02_CMD_FAULT: G03_RelayStop();','case G02_CMD_FAULT: G03_PWM_Stop(); G03_RelayStop();'),
 ('case G02_CMD_COMPARE: g02_command_result = G02_SetCompare','case G02_CMD_COMPARE: if(G03_PWM_Blocks()){g02_command_result=G02_BUSY;break;} g02_command_result = G02_SetCompare'),
 ('    if (G03_ADC_IRQHandler()) return 1;','    if (G03_PWM_ADCIRQ()) return 1;\n    if (G03_ADC_IRQHandler()) return 1;')])
edit('BSP/g03_port.c',[
 ('return G03_RelayBusy() ||','return G03_PWM_Blocks() || G03_RelayBusy() ||'),
 ('if(op==13U && !arg){G03_RelayStop();','if(op==13U && !arg){G03_PWM_Stop();G03_RelayStop();'),
 ('else if(G03_RelayBusy()||','else if(G03_PWM_Blocks()||G03_RelayBusy()||')])
edit('BSP/g03_adc_port.c',[('if(G03_RelayBusy()||','if(G03_PWM_Blocks()||G03_RelayBusy()||')])
edit('BSP/g03_relay_port.c',[('if(G03_RelayBusy()||G02_OwnsADC','if(G03_PWM_Blocks()||G03_RelayBusy()||G02_OwnsADC')])
edit('Appli/Core/Src/main.c',[
 ('#include "g03_relay_port.h"','#include "g03_relay_port.h"\n#include "g03_pwm_port.h"'),
 ('    G03_RelayInit();','    G03_RelayInit();\n    G03_PWM_Init();'),
 ('    G03_ADC_Task();','    G03_PWM_Task();\n    G03_ADC_Task();')])
edit('Appli/Core/Src/stm32n6xx_it.c',[
 ('#include "g03_relay_port.h"','#include "g03_relay_port.h"\n#include "g03_pwm_port.h"'),
 ('  G03_RelayTickIRQ();','  if (!G03_PWM_TimerIRQ()) G03_RelayTickIRQ();')])
p=ROOT/'BSP/g02_link.c';s=p.read_text(encoding='utf-8')
s=s.replace('reply_adc,reply_op,reply_arg,reply_relay;','reply_adc,reply_op,reply_arg,reply_relay,reply_pwm;')
s=s.replace('++bad_frames;', '++bad_frames;G03_PWM_ProtocolFault();')
s=s.replace('overflow=1U; return;', 'overflow=1U; G03_PWM_ProtocolFault(); return;')
s=s.replace('void G02_LinkRxError(void) { overflow=1U; }','void G02_LinkRxError(void) { overflow=1U; G03_PWM_ProtocolFault(); }')
s=s.replace('reply_id=id; pending=1U;', 'reply_id=id; pending=1U;reply_pwm=op>=40U && op<=49U;')
s=s.replace('if(id<last_id) {reply_code=7U;return;}', 'if(id<last_id) {reply_code=7U;G03_PWM_ProtocolFault();return;}')
s=s.replace('if(id==last_id) {reply_code=(op==last_op&&arg==last_arg)?last_code:8U;return;}',
 '''if(id==last_id) {reply_code=(op==last_op&&arg==last_arg)?last_code:8U;
        if(reply_code==8U)G03_PWM_ProtocolFault();return;}''')
s=s.replace('    if(reply_relay){reply_code=', '    if(reply_pwm){reply_code=G03_PWM_Command(op,arg,id);last_code=reply_code;return;}\n    if(reply_relay){reply_code=')
s=s.replace('    if(reply_relay){\n', '''    if(reply_pwm){
        n=G03_PWM_Report(out,sizeof out,reply_id,reply_code,reply_op,reply_arg);
        if(n>0 && n<(int)sizeof out)uart_printf("%s*%04X\\r\\n",out,(unsigned)crc16(out,(uint32_t)n));
        return;
    }
    if(reply_relay){
''')
s=s.replace('if(pending && !G03_RelayBusy()', 'if(pending && !G03_PWM_Busy() && !G03_PWM_Owns() && !G03_RelayBusy()')
p.write_text(s,encoding='utf-8',newline='\n')
print('Integrated one-shot hooks, exclusive ownership, identities and protocol in staging')
