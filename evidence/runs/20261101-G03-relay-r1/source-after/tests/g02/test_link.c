#define main test_port_baseline_main
#include "test_port.c"
#undef main
#include "g02_link.h"
#include <stdarg.h>
static char reply[512];
void uart_printf(const char *fmt, ...) {va_list ap;va_start(ap,fmt);vsnprintf(reply,sizeof reply,fmt,ap);va_end(ap);}
static unsigned checksum(const char *p)
{unsigned crc=65535U,i;while(*p){crc^=(unsigned char)*p++<<8;for(i=0;i<8;i++)crc=((crc&32768U)?(crc<<1)^0x1021U:crc<<1)&65535U;}return crc;}
static void send_command(unsigned id,unsigned op,unsigned arg)
{char s[80],frame[100];unsigned i;snprintf(s,sizeof s,"G02,%u,%u,%u",id,op,arg);snprintf(frame,sizeof frame,"%s*%04X\n",s,checksum(s));reply[0]=0;
 for(i=0;frame[i];i++){G02_LinkRx((const uint8_t *)&frame[i],1);G02_LinkTask();}}
static void expect(unsigned id,unsigned result)
{char prefix[70];snprintf(prefix,sizeof prefix,"#G02,g03-relay-r1,%u,%u,",id,result);assert(strncmp(reply,prefix,strlen(prefix))==0);}
#ifndef G02_LINK_MAIN
#define G02_LINK_MAIN main
#endif
int G02_LINK_MAIN(void)
{
 unsigned start; char huge[300];
 assert(test_port_baseline_main()==0);
 send_command(1,0,0);expect(1,0);
 send_command(2,1,1000);assert(g02_control.state==G02_STATE_RUNNING && !reply[0]);start=g02_telemetry.start_ms;
 send_command(2,1,1000);assert(g02_telemetry.start_ms==start);
 send_command(3,5,1500);assert(TIM1->CCR2==1500 && !reply[0]);
 send_command(4,2,0);expect(4,0);assert_off();
 send_command(2,1,1000);expect(2,7);assert_off();
 send_command(4,1,1000);expect(4,8);assert_off();
 send_command(5,3,0);expect(5,0);assert(g02_control.faults&G02_FAULT_INJECTED);
 send_command(6,1,1000);expect(6,G02_FAULTED);assert_off();
 send_command(7,4,0);expect(7,0);assert_off();
 G02_LinkRx((const uint8_t *)"G02,999,1,1000*0000\n",20);G02_LinkTask();assert_off();
 send_command(8,99,0);expect(8,G02_BAD_ARGUMENT);assert_off();
 memset(huge,'x',sizeof huge);G02_LinkRx((const uint8_t *)huge,sizeof huge);G02_LinkTask();
 G02_LinkRx((const uint8_t *)"\n",1);G02_LinkTask();send_command(9,0,0);expect(9,0);
 G02_LinkRxError();G02_LinkTask();G02_LinkRx((const uint8_t *)"\n",1);G02_LinkTask();
 send_command(10,1,0);expect(10,G02_BAD_ARGUMENT);assert_off();
 send_command(11,1,10001);expect(11,G02_BAD_ARGUMENT);assert_off();
 send_command(12,1,10);tick+=10;G02_Task();G02_LinkTask();expect(12,0);assert_off();
 start=g02_compare;
 send_command(13,5,1999);expect(13,G02_NOT_READY);assert_off();
 assert(g02_compare==start); /* A rejected command must not change the next START. */
 puts(reply);puts("PASS: CRC/fragments/overflow/replay/quiet-run/STOP/fault/clear/timeout transport using production core+port+link.");return 0;
}
