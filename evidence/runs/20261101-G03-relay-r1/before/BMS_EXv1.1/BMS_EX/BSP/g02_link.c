/* G02-only receive/diagnostic transport. Never exposes PINS or relay control. */
#include "g02_link.h"
#include "g02_port.h"
#include "g03_port.h"
#include "g03_adc_port.h"
#include "main.h"
#include <stdio.h>
#include <string.h>
extern void uart_printf(const char *fmt, ...);
#define RX_SIZE 256U
static uint8_t rx[RX_SIZE];
static volatile uint32_t head, tail, overflow;
static char line[64];
static uint32_t used, dropping, last_id, last_op, last_arg, reply_id, reply_code;
static uint32_t reply_adc,reply_op,reply_arg;
static uint32_t start_id, pending, bad_frames, rx_errors, last_code, reply_g03;
static uint16_t crc16(const char *p, uint32_t n)
{
    uint16_t crc=0xffffU; uint32_t i;
    while(n--) { crc ^= (uint16_t)((uint16_t)(uint8_t)*p++ << 8);
        for(i=0;i<8U;++i) crc=(uint16_t)((crc&0x8000U)?((uint32_t)crc<<1)^0x1021U:(uint32_t)crc<<1); }
    return crc;
}
void G02_LinkRx(const uint8_t *data, uint16_t size)
{
    uint32_t next;
    while(size--) {
        next=(head+1U)%RX_SIZE;
        if(overflow || next==tail) { overflow=1U; return; }
        rx[head]=*data++; head=next;
    }
}
void G02_LinkRxError(void) { overflow=1U; }
static int number(const char **s, uint32_t *v, char delimiter)
{
    uint32_t n=0, digit; const char *p=*s;
    if(*p<'0'||*p>'9') return 0;
    do {digit=(uint32_t)(*p++-'0'); if(n>(0xffffffffU-digit)/10U)return 0; n=n*10U+digit;}
    while(*p>='0'&&*p<='9');
    if(*p!=delimiter)return 0;
    *s=p+1; *v=n; return 1;
}
static void execute(void)
{
    const char *p=line+4, *star;
    uint32_t id,op,arg,i,wire=0,previous_compare,previous_window; char c;
    if(strncmp(line,"G02,",4)!=0 || !number(&p,&id,',') || !number(&p,&op,',') ||
       !number(&p,&arg,'*') || !id || strlen(p)!=4U) { ++bad_frames; return; }
    star=p-1;
    for(i=0;i<4U;++i) { c=*p++; if(c>='0'&&c<='9')wire=wire*16U+(uint32_t)(c-'0');
        else if(c>='A'&&c<='F')wire=wire*16U+(uint32_t)(c-'A'+10);
        else {++bad_frames;return;} }
    if(wire!=crc16(line,(uint32_t)(star-line))) {++bad_frames;return;}
    reply_id=id; pending=1U;reply_g03=op>=10U && op<=19U;
    reply_adc=op>=20U && op<=29U;reply_op=op;reply_arg=arg;
    if(id<last_id) {reply_code=7U;return;}
    if(id==last_id) {reply_code=(op==last_op&&arg==last_arg)?last_code:8U;return;}
    last_id=id; last_op=op; last_arg=arg;
    if(reply_adc){reply_code=G03_ADC_Command(op,arg);last_code=reply_code;return;}
    if(reply_g03){reply_code=G03_Command(op,arg);last_code=reply_code;return;}
    /* Wire ops: 0 status, 1 sample(ms), 2 stop, 3 fault, 4 clear,
     * 5 compare. There is deliberately no pin-output operation. */
    reply_code=G02_BAD_ARGUMENT; last_code=reply_code;
    if(op==0U && arg==0U) {reply_code=G02_OK;last_code=reply_code;return;}
    previous_compare=g02_compare;previous_window=g02_window_ms;
    if(op==1U) {
        if(!arg||arg>G02_MAX_WINDOW_MS)return;
        if(G03_BlocksG02()){reply_code=G02_BUSY;last_code=reply_code;return;}
        g02_window_ms=arg; g02_command=G02_CMD_SAMPLE;
    } else if(op==5U) {
        if(!arg||arg>=2000U)return;
        g02_compare=arg;g02_command=G02_CMD_COMPARE;
    } else if(arg==0U && op>=2U && op<=4U)
        g02_command=op==2U?G02_CMD_STOP:(op==3U?G02_CMD_FAULT:G02_CMD_CLEAR);
    else return;
    if(op==2U)(void)G03_Command(13U,0U);
    G02_Task(); reply_code=(uint32_t)g02_command_result;last_code=reply_code;
    if(reply_code!=G02_OK) {
        g02_compare=previous_compare;g02_window_ms=previous_window;
    }
    if(op==1U && reply_code==G02_OK)start_id=id;
}
static void report(void)
{
    /* Foreground-only, non-reentrant. Keep large diagnostics off the 2 KiB
     * Cortex-M stack (r1 live status request exposed STKOF at MSPLIM). */
    static char out[1024]; int n;
    if(reply_adc){
        n=G03_ADC_Report(out,sizeof out,reply_id,reply_code,reply_op,reply_arg);
        if(n>0 && n<(int)sizeof out)uart_printf("%s*%04X\r\n",out,(unsigned)crc16(out,(uint32_t)n));
        return;
    }
    if(reply_g03){
        n=G03_Report(out,sizeof out,reply_id,reply_code);
        if(n>0 && n<(int)sizeof out)uart_printf("%s*%04X\r\n",out,(unsigned)crc16(out,(uint32_t)n));
        return;
    }
    /* Called only when TIM session stopped, including failed ADC cleanup.
     * No TX/formatting in fast ISRs or in the sampling window. */
    n=snprintf(out,sizeof out,
        "#G02,g03-adc-r4,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu",
        (unsigned long)reply_id,(unsigned long)reply_code,(unsigned long)start_id,
        (unsigned long)g02_control.state,(unsigned long)g02_control.faults,
        (unsigned long)G02_OwnsADC(&g02_control),(unsigned long)g02_telemetry.cpu_hz,
        (unsigned long)g02_telemetry.tim_hz,(unsigned long)g02_telemetry.adc_hz,
        (unsigned long)g02_telemetry.start_ms,(unsigned long)g02_telemetry.stop_ms,
        (unsigned long)g02_telemetry.update_irqs,(unsigned long)g02_telemetry.adc_completions,
        (unsigned long)g02_telemetry.overruns,(unsigned long)g02_telemetry.adc_errors,
        (unsigned long)g02_telemetry.update_gap_max_cycles,(unsigned long)g02_telemetry.update_isr_max_cycles,
        (unsigned long)g02_telemetry.adc_isr_max_cycles,(unsigned long)g02_telemetry.late_update_irqs,
        (unsigned long)g02_telemetry.ccr_writes,(unsigned long)g02_telemetry.ccr_requested,
        (unsigned long)g02_telemetry.ccr_next_uev_observed,
        (unsigned long)(g02_telemetry.stop_cycles-g02_telemetry.stop_request_cycles),
        (unsigned long)bad_frames,(unsigned long)rx_errors,(unsigned long)G02_ALLOW_PIN_OUTPUT);
    if(n>0 && n<(int)sizeof out)uart_printf("%s*%04X\r\n",out,(unsigned)crc16(out,(uint32_t)n));
}
void G02_LinkTask(void)
{
    uint8_t c; uint32_t key;
    if(overflow) {
        key=__get_PRIMASK();__disable_irq();tail=head;overflow=0;__set_PRIMASK(key);
        ++rx_errors;used=0;dropping=1;
    }
    while(tail!=head) {
        c=rx[tail];tail=(tail+1U)%RX_SIZE;
        if(c=='\n') {
            if(!dropping) {line[used]=0;execute();}
            used=0;dropping=0;
        } else if(!dropping) {
            if(c<' '||c>'~'||used>=sizeof(line)-1U) {dropping=1;used=0;++bad_frames;}
            else line[used++]=(char)c;
        }
    }
    if(pending && g02_control.state!=G02_STATE_RUNNING && g02_control.state!=G02_STATE_STARTING) {
        pending=0;report();
    }
}
