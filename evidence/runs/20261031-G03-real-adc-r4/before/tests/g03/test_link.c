#define G02_LINK_MAIN baseline_link_main
#include "../g02/test_link.c"
#include "g03_port.h"
static void g03_expect(unsigned id,unsigned code)
{char prefix[80];snprintf(prefix,sizeof prefix,"#G03,g03-adc-r3,%u,%u,",id,code);assert(strncmp(reply,prefix,strlen(prefix))==0);puts(reply);}
static void advance(unsigned n){while(n--){++tick;G03_TickIRQ();assert_off();}}
int main(void)
{
 assert(baseline_link_main()==0);G03_PortInit();
 send_command(20,17,1);g03_expect(20,0);
 send_command(21,11,2000);g03_expect(21,0);advance(60);
 send_command(22,1,100);expect(22,G02_BUSY);assert(g02_control.state==G02_STATE_STOPPED);
 send_command(23,15,0);g03_expect(23,0);advance(400);
 send_command(23,15,0);g03_expect(23,0);advance(400);
 send_command(24,10,0);g03_expect(24,0);
 send_command(25,12,100);g03_expect(25,G03_FAULTED);
 send_command(26,14,0);g03_expect(26,0);
 send_command(27,18,1);g03_expect(27,G03_DISALLOWED);
 send_command(28,11,1000);g03_expect(28,0);advance(60);
 send_command(29,2,0);expect(29,0);advance(20);
 send_command(30,10,0);g03_expect(30,0);assert(!G03_BlocksG02());
 puts("PASS: production UART G03 dispatch, replay does not heartbeat, G02 exclusion and shared STOP.");return 0;
}
