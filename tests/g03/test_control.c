#include "g03_control.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static G03Control c;
static const G03Config cfg={1,20,30,20,200,800,100,10000,400,1600,3000,4200,500,500,0,45000,20};
static G03Sample s;
static void fresh(uint32_t t){s.valid=s.calibrated=1;s.at_ms=t;s.cell_mv[0]=s.cell_mv[1]=s.cell_mv[2]=3600;s.current_ma=0;s.temp_mc=25000;}
static void init(void){memset(&c,0,sizeof c);G03_Init(&c);fresh(0);assert(G03_Configure(&c,&cfg)==0);}
static void step(uint32_t t){fresh(t);G03_Tick(&c,t,&s,0);}
static void running(uint32_t direction){init();assert(G03_Start(&c,direction,1000,0,&s)==0);step(20);assert(c.state==G03_RELAY_WAIT&&!c.shadow_pwm&&c.shadow_relays==direction);step(50);assert(c.shadow_pwm&&c.shadow_relays==direction);}
static void fault(uint32_t expected){G03_Tick(&c,51,&s,0);assert(c.state==G03_FAULT&&(c.faults&expected)&&!c.shadow_pwm&&!c.shadow_relays);assert(G03_Start(&c,1,100,52,&s)==G03_FAULTED);assert(G03_Clear(&c)==0);assert(c.state==G03_STOPPED&&!c.shadow_pwm&&!c.shadow_relays);}
int main(void)
{
 unsigned i;uint32_t seed=7,t=0;G03Config bad;
 memset(&c,0,sizeof c);G03_Init(&c);fresh(0);assert(G03_Start(&c,1,100,0,&s)==G03_NOT_READY);
 init();bad=cfg;bad.known=0;assert(G03_Configure(&c,&bad)==G03_BAD_ARGUMENT);assert(c.configured);
 assert(G03_Compare(&c,399)==G03_BAD_ARGUMENT&&c.ccr==1000);
 assert(G03_Start(&c,0,100,0,&s)==G03_BAD_ARGUMENT);
 assert(G03_Start(&c,1,10001,0,&s)==G03_BAD_ARGUMENT);
 for(i=1;i<=2;i++){
  running(i);assert(c.state==(i==1?G03_CHARGE:G03_DISCHARGE));
  assert(G03_Start(&c,3-i,1,50,&s)==G03_BUSY&&c.direction==i&&c.duration_ms==1000);
  assert(G03_Compare(&c,1200)==0&&c.ccr==1200);
  G03_Stop(&c,60,G03_REASON_STOP);assert(c.state==G03_DECAY_WAIT&&!c.shadow_pwm&&c.shadow_relays==i);
  G03_Stop(&c,70,G03_REASON_STOP);assert(c.entered_ms==60);
  assert(G03_Start(&c,3-i,100,70,&s)==G03_BUSY);step(80);assert(c.state==G03_STOPPED&&!c.shadow_relays);
 }
 running(1);fresh(51);s.valid=0;fault(G03_F_SENSOR);
 running(1);fresh(51);s.calibrated=0;fault(G03_F_SENSOR);
 running(1);fresh(51-101U);fault(G03_F_STALE);
 running(1);fresh(51);s.current_ma=501;fault(G03_F_CURRENT);
 running(2);fresh(51);s.current_ma=-501;fault(G03_F_CURRENT);
 running(1);fresh(51);s.current_ma=-21;fault(G03_F_REVERSE);
 running(2);fresh(51);s.current_ma=21;fault(G03_F_REVERSE);
 for(i=0;i<3;i++){running(1);fresh(51);s.cell_mv[i]=2999;fault(G03_F_UV);running(1);fresh(51);s.cell_mv[i]=4201;fault(G03_F_OV);}
 running(1);fresh(51);s.temp_mc=-1;fault(G03_F_TEMP);
 running(1);fresh(51);s.temp_mc=45001;fault(G03_F_TEMP);
 running(1);step(799);assert(c.state==G03_CHARGE);step(800);assert(c.faults&G03_F_LINK);
 running(1);assert(G03_Heartbeat(&c,800)==G03_FAULTED);assert(c.faults&G03_F_LINK);
 running(1);assert(G03_Heartbeat(&c,700)==0);step(1000);assert(c.state==G03_DECAY_WAIT&&c.reason==G03_REASON_DURATION);step(1020);assert(c.state==G03_STOPPED);
 running(1);fresh(51);G03_Tick(&c,51,&s,1);assert(c.faults&G03_F_INTERLOCK);
 running(1);c.shadow_relays=3;fresh(51);G03_Tick(&c,51,&s,0);assert(c.faults&G03_F_INTERLOCK);
 running(1);G03_Stop(&c,60,G03_REASON_STOP);fresh(260);s.current_ma=100;G03_Tick(&c,260,&s,0);assert(c.faults&G03_F_DECAY);
 init();fresh(0xfffffff0U);assert(G03_Start(&c,1,200,0xfffffff0U,&s)==0);step(4);step(34);assert(c.state==G03_CHARGE);step(184);step(204);assert(c.state==G03_STOPPED);
 running(1);G03_Init(&c);assert(c.faults&G03_F_EXTERNAL);
 init();for(i=0;i<10000;i++){
  seed=seed*1664525U+1013904223U;t+=seed%5U;fresh(t);
  switch(seed%7U){case 0:(void)G03_Start(&c,1+((seed>>8)&1U),100,t,&s);break;case 1:G03_Stop(&c,t,G03_REASON_STOP);break;case 2:(void)G03_Clear(&c);break;case 3:(void)G03_Heartbeat(&c,t);break;case 4:G03_Fault(&c,G03_F_EXTERNAL,t);break;case 5:(void)G03_Compare(&c,seed%2001);break;default:break;}
  G03_Tick(&c,t,&s,0);
  assert(c.shadow_relays<=2U);
  assert(!c.shadow_pwm||((c.state==G03_CHARGE||c.state==G03_DISCHARGE)&&c.shadow_relays==c.direction));
  assert((c.state!=G03_FAULT&&c.state!=G03_STOPPED)||(!c.shadow_pwm&&!c.shadow_relays));
 }
 puts("PASS: G03 shadow state, interlocks, signed limits, freshness, local timeout, duration, decay, wrap and 10000 event-sequence invariants.");return 0;
}
