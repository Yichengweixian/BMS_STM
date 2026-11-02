#define ADC_PORT_MAIN adc_port_main
#include "test_adc_port.c"
#undef main
#include "g02_link.h"
#include <stdarg.h>
static char reply[1300];
void uart_printf(const char *fmt,...)
{va_list a;va_start(a,fmt);vsnprintf(reply,sizeof reply,fmt,a);va_end(a);}
static unsigned crc(const char *s)
{unsigned c=65535,i;while(*s){c^=(unsigned)(unsigned char)*s++<<8;for(i=0;i<8;i++)c=((c<<1)^((c&32768)?0x1021:0))&65535;}return c;}
static void send(unsigned id,unsigned op,unsigned arg)
{char b[80],w[90];snprintf(b,sizeof b,"G02,%u,%u,%u",id,op,arg);snprintf(w,sizeof w,"%s*%04X\n",b,crc(b));
 G02_LinkRx((const uint8_t *)w,(uint16_t)strlen(w));G02_LinkTask();}
static void expect(unsigned id,unsigned code,const char *kind)
{char b[90];snprintf(b,sizeof b,"%s,g03-relay-r2,%u,%u,",kind,id,code);assert(strncmp(reply,b,strlen(b))==0);puts(reply);}
#ifndef ADC_LINK_MAIN
#define ADC_LINK_MAIN main
#endif
int ADC_LINK_MAIN(void)
{
 unsigned i;assert(adc_port_main()==0);
 send(100,21,5);expect(100,0,"#G3D");send(101,22,0);expect(101,0,"#G3A");
 send(102,24,2000);expect(102,0,"#G3A");send(103,25,0);expect(103,0,"#G3A");
 for(i=0;i<450;i++){conversion(2048);++tick;G03_ADC_TickIRQ();}
 send(103,25,0);expect(103,0,"#G3A");
 for(i=0;i<450;i++){if(G03_ADC_Owns()&&!status_fault())conversion(2048);++tick;G03_ADC_TickIRQ();}
 assert(status_fault()&G3A_LINK);G03_ADC_Task();send(104,20,0);expect(104,0,"#G3A");
 send(105,28,0);expect(105,0,"#G3T");send(106,27,0);expect(106,0,"#G3A");
 send(107,18,1);expect(107,G03_DISALLOWED,"#G03");assert_off();
 puts("PASS: real ADC production UART dispatch, CRC reports, replay heartbeat and power rejection");return 0;
}
