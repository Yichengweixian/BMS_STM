#define main baseline_main
#include "../g02/test_port.c"
#undef main
#include "g03_port.h"
static void advance(unsigned ms){while(ms--){++tick;G03_TickIRQ();assert_off();}}
int main(void)
{
 char report[480];unsigned scenario;static const unsigned bits[]={0,2,4,8,16,32,64,256,1024,512,2};
 assert(baseline_main()==0);G03_PortInit();
 assert(G03_Command(11,1000)==G03_NOT_READY);assert(G03_Command(18,1)==G03_DISALLOWED);
 assert(G03_Command(17,1)==0);assert(G03_Command(11,1000)==0);advance(60);
 assert(G03_BlocksG02());g02_command=G02_CMD_SAMPLE;G02_Task();assert(g02_command_result==G02_BUSY);assert_off();
 advance(740);assert(G03_BlocksG02());G03_Report(report,sizeof report,1,0);puts(report);
 assert(G03_Command(11,100)==G03_FAULTED);assert(G03_Command(14,0)==0);
 for(scenario=1;scenario<=10;scenario++){
  assert(G03_Command(16,0)==0);assert(G03_Command(12,1000)==0);advance(60);
  assert(G03_Command(16,scenario)==0);
  if(scenario==9){assert(G03_Command(13,0)==0);advance(200);}else advance(1);
  assert(G03_Command(12,100)==G03_FAULTED);G03_Report(report,sizeof report,scenario,bits[scenario]);puts(report);
  assert(G03_Command(14,0)==0);assert_off();
 }
 assert(G03_Command(16,0)==0);assert(G03_Command(17,0)==0);
 assert(G03_Command(12,100)==G03_NOT_READY);
 g02_command=G02_CMD_SAMPLE;G02_Task();assert(g02_command_result==0);
 assert(G03_Command(11,100)==G03_BUSY);assert(G03_Command(13,0)==0);assert(G02_MeasurementAllowed());assert_off();
 puts("PASS: production G03 tick adapter, synthesized faults and G02 mutual exclusion; every tick keeps registers off.");return 0;
}
