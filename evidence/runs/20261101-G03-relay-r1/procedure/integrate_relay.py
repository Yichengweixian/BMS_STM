from pathlib import Path
root=Path(__file__).parent
bsp=root/'BMS_EXv1.1/BMS_EX/BSP'
def edit(p,old,new,count=None):
    s=p.read_text(encoding='utf-8-sig')
    assert old in s,(p,old)
    if count is not None: assert s.count(old)==count,(p,s.count(old))
    p.write_text(s.replace(old,new),encoding='utf-8')
for name in ['g02_port.c','g02_link.c','g03_port.c','g03_adc_port.c']:
    edit(bsp/name,'#include "g03_adc_port.h"','#include "g03_adc_port.h"\n#include "g03_relay_port.h"',1)
edit(bsp/'g02_port.c','return !G03_ADC_Owns()','return !G03_RelayBusy() && !G03_ADC_Owns()',1)
edit(bsp/'g02_port.c','void G02_CPUFault(void)\n{','void G02_CPUFault(void)\n{\n    G03_RelayCPUFault();',1)
edit(bsp/'g02_port.c','case G02_CMD_STOP: G02_Stop','case G02_CMD_STOP: G03_RelayStop(); G02_Stop',1)
edit(bsp/'g02_port.c','case G02_CMD_FAULT: G02_Fault','case G02_CMD_FAULT: G03_RelayStop(); G02_Fault',1)
edit(bsp/'g03_port.c','return G03_SyntheticBusy() ||','return G03_RelayBusy() || G03_SyntheticBusy() ||',1)
edit(bsp/'g03_port.c','if(op==13U && !arg){G03_ADC_Stop();','if(op==13U && !arg){G03_RelayStop();G03_ADC_Stop();',1)
edit(bsp/'g03_port.c','else if(G03_ADC_BlocksOthers()','else if(G03_RelayBusy()||G03_ADC_BlocksOthers()',1)
edit(bsp/'g03_adc_port.c','if(G02_OwnsADC(&g02_control)||','if(G03_RelayBusy()||G02_OwnsADC(&g02_control)||',1)
edit(bsp/'g02_link.c','/* G02-only receive/diagnostic transport. Never exposes PINS or relay control. */','/* Shared CRC/id transport; relay commands have an independent one-shot gate. */',1)
edit(bsp/'g02_link.c','static uint32_t reply_adc,reply_op,reply_arg;','static uint32_t reply_adc,reply_op,reply_arg,reply_relay;',1)
edit(bsp/'g02_link.c','reply_adc=op>=20U && op<=29U;','reply_relay=op>=30U && op<=39U;reply_adc=op>=20U && op<=29U;',1)
edit(bsp/'g02_link.c','if(reply_adc){reply_code=','if(reply_relay){reply_code=G03_RelayCommand(op,arg);last_code=reply_code;return;}\n    if(reply_adc){reply_code=',1)
edit(bsp/'g02_link.c','static char out[1024]; int n;','static char out[1024]; int n;\n    if(reply_relay){\n        n=G03_RelayReport(out,sizeof out,reply_id,reply_code,reply_op,reply_arg);\n        if(n>0 && n<(int)sizeof out)uart_printf("%s*%04X\\r\\n",out,(unsigned)crc16(out,(uint32_t)n));\n        return;\n    }',1)
edit(bsp/'g02_link.c','if(pending && g02_control.state','if(pending && !G03_RelayBusy() && g02_control.state',1)
main=root/'BMS_EXv1.1/BMS_EX/Appli/Core/Src/main.c'
edit(main,'#include "g03_adc_port.h"','#include "g03_adc_port.h"\n#include "g03_relay_port.h"',1)
edit(main,'    G03_PortInit();','    G03_PortInit();\n    G03_RelayInit();',1)
edit(main,'    G02_LinkTask();','    G02_LinkTask();\n    G03_RelayTask();',1)
it=root/'BMS_EXv1.1/BMS_EX/Appli/Core/Src/stm32n6xx_it.c'
edit(it,'#include "g03_adc_port.h"','#include "g03_adc_port.h"\n#include "g03_relay_port.h"',1)
edit(it,'  HAL_TIM_IRQHandler(&htim2);','  G03_RelayTickIRQ();',1)
proj=root/'BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/BMS_EX_Appli.uvprojx'
needle='<File><FileName>g03_adc_port.c</FileName><FileType>1</FileType><FilePath>..\\..\\BSP\\g03_adc_port.c</FilePath></File>'
edit(proj,needle,needle+''.join('\n              <File><FileName>'+n+'</FileName><FileType>1</FileType><FilePath>..\\..\\BSP\\'+n+'</FilePath></File>' for n in ['g03_relay_core.c','g03_relay_port.c']),2)
# Identity is shared by legacy schemas; keep older captures readable.
for n in ['g02_link.c','g03_port.c','g03_adc_port.c','measurement.c']:
    edit(bsp/n,'g03-adc-r4','g03-relay-r1')
for p in list((root/'scripts').rglob('*.py'))+list((root/'tests').rglob('*.py'))+list((root/'tests').rglob('*.c')):
    s=p.read_text(encoding='utf-8-sig')
    if 'g03-adc-r4' in s:
        # New output identity in fixtures; parser accepted sets retain r4 below.
        p.write_text(s.replace('g03-adc-r4','g03-relay-r1'),encoding='utf-8')
for p in (root/'scripts').rglob('*.py'):
    s=p.read_text()
    s=s.replace("v[1]!='g03-relay-r1'","v[1] not in ('g03-adc-r4','g03-relay-r1')")
    s=s.replace("'g03-relay-r1')","'g03-adc-r4','g03-relay-r1')") if "'g03-adc-r4'" not in s else s
    p.write_text(s,encoding='utf-8')
# Existing subsystem tests use an explicit inactive relay fixture. New tests cover real adapter separately.
stub=root/'tests/g03/relay_bridge_stub.c'
stub.write_text('''#include "g03_relay_port.h"
void G03_RelayInit(void){}
int G03_RelayBusy(void){return 0;}
void G03_RelayTask(void){}
void G03_RelayTickIRQ(void){}
void G03_RelayStop(void){}
void G03_RelayCPUFault(void){}
uint32_t G03_RelayCommand(uint32_t op,uint32_t arg){(void)op;(void)arg;return 4U;}
int G03_RelayReport(char *o,unsigned s,uint32_t i,uint32_t r,uint32_t p,uint32_t a)
{(void)o;(void)s;(void)i;(void)r;(void)p;(void)a;return -1;}
''')
for rel in ['scripts/g02/run_checks.py','scripts/g03/run_checks.py','scripts/g03/run_adc_checks.py']:
    p=root/rel;s=p.read_text()
    s=s.replace("bsp / 'g02_port.c',","bsp / 'g02_port.c', root / 'tests/g03/relay_bridge_stub.c',")
    s=s.replace("bsp/'g02_port.c',","bsp/'g02_port.c',root/'tests/g03/relay_bridge_stub.c',")
    p.write_text(s,encoding='utf-8')
print('relay integration applied')
