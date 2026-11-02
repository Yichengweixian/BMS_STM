#include "g03_adc_core.h"
#include "nominal_current.h"
#include <string.h>
#include <math.h>
int32_t G3A_CurrentUA(uint32_t raw,uint32_t zero_mcode)
{
    double ua=((double)raw-(double)zero_mcode/1000.0)*CURRENT_MCU_LSB*CURRENT_HEX_GAIN*1000000.0;
    return (int32_t)(ua+(ua<0.0?-0.5:0.5));
}
int G3A_Window(uint32_t zero,uint32_t ma,uint32_t *low,uint32_t *high)
{
    double delta,lo,hi;
    if(!low||!high||zero<1000U||zero>4094000U||!ma||ma>2000U)return 0;
    delta=(double)ma/(CURRENT_HEX_GAIN*1000.0*CURRENT_MCU_LSB);
    lo=ceil((double)zero/1000.0-delta);hi=floor((double)zero/1000.0+delta);
    /* Reject an unobservable limit. Never clamp it to an ADC rail. */
    if(lo<1.0||hi>4094.0||lo>=hi)return 0;
    *low=(uint32_t)lo;*high=(uint32_t)hi;return 1;
}
static void record(G3ACore *c,uint32_t event,uint32_t now,uint32_t cycles)
{
    G3AEvent *e=&c->trace[c->written%G3A_TRACE_SIZE];
    e->seq=c->written;e->ms=now;e->cycles=cycles;e->raw=c->raw;e->ua=c->ua;
    e->ccr=c->ccr;e->event=event;e->faults=c->faults;
    if(c->written>=G3A_TRACE_SIZE)++c->overwritten;
    ++c->written;
}
int G3A_Configure(G3ACore *c,uint32_t zero,uint32_t ma)
{
    uint32_t lo,hi;
    if(c->state!=G3A_IDLE||!G3A_Window(zero,ma,&lo,&hi))return 0;
    c->zero_mcode=zero;c->limit_ma=ma;c->low=lo;c->high=hi;c->configured=1;return 1;
}
int G3A_Start(G3ACore *c,uint32_t duration,uint32_t now,uint32_t cycles,uint32_t probe)
{
    if(c->state!=G3A_IDLE||!c->configured||duration<100U||duration>2000U||probe>2U)return 0;
    c->state=G3A_RUNNING;c->faults=0;c->reason=0;c->start_ms=now;c->last_ms=now;
    c->heartbeat_ms=now;c->duration_ms=duration;c->count=0;c->step=0;c->ccr=1800;
    c->raw=0;c->ua=INT32_MIN;c->written=0;c->overwritten=0;c->trip_ms=0;c->trip_cycles=0;c->probe=probe;
    record(c,G3A_START,now,cycles);return 1;
}
void G3A_Trip(G3ACore *c,uint32_t fault,uint32_t now,uint32_t cycles)
{
    if(c->state!=G3A_RUNNING)return;
    c->faults|=fault;c->state=G3A_FAULT;c->reason=3;c->trip_ms=now;c->trip_cycles=cycles;
    record(c,G3A_TRIP,now,cycles);c->ccr=0;
}
void G3A_Stop(G3ACore *c,uint32_t now,uint32_t cycles,uint32_t reason)
{
    if(c->state!=G3A_RUNNING)return;
    c->state=G3A_IDLE;c->reason=reason;record(c,G3A_STOP,now,cycles);c->ccr=0;
}
void G3A_Sample(G3ACore *c,uint32_t raw,uint32_t flags,uint32_t now,uint32_t cycles)
{
    if(c->state!=G3A_RUNNING)return;
    c->raw=raw;c->last_ms=now;++c->count;
    if(raw>0U&&raw<4095U)c->ua=G3A_CurrentUA(raw,c->zero_mcode);
    else {flags|=G3A_RANGE;c->ua=INT32_MIN;}
    if(raw<c->low||raw>c->high)flags|=G3A_CURRENT;
    if(flags){G3A_Trip(c,flags,now,cycles);return;}
    if(c->count==1U||c->count%10U==0U)record(c,G3A_SAMPLE,now,cycles);
}
void G3A_Tick(G3ACore *c,uint32_t now,uint32_t cycles)
{
    uint32_t elapsed,step;
    if(c->state!=G3A_RUNNING)return;
    if((uint32_t)(now-c->last_ms)>5U){G3A_Trip(c,G3A_STALE,now,cycles);return;}
    if((uint32_t)(now-c->heartbeat_ms)>=800U){G3A_Trip(c,G3A_LINK,now,cycles);return;}
    elapsed=now-c->start_ms;
    if(elapsed>=c->duration_ms){G3A_Stop(c,now,cycles,1);return;}
    step=elapsed*5U/c->duration_ms;
    if(step!=c->step){c->step=step;c->ccr=1800U-step*100U;record(c,G3A_STEP,now,cycles);}
}
int G3A_Heartbeat(G3ACore *c,uint32_t now,uint32_t cycles)
{
    if(c->state!=G3A_RUNNING)return 0;
    if((uint32_t)(now-c->heartbeat_ms)>=800U){G3A_Trip(c,G3A_LINK,now,cycles);return 0;}
    c->heartbeat_ms=now;return 1;
}
int G3A_Clear(G3ACore *c)
{
    if(c->state==G3A_RUNNING)return 0;
    c->state=G3A_IDLE;c->faults=0;c->ccr=0;c->configured=0;return 1;
}
int G3A_Read(const G3ACore *c,uint32_t seq,G3AEvent *e)
{
    if(!e||seq<c->overwritten||seq>=c->written)return 0;
    *e=c->trace[seq%G3A_TRACE_SIZE];return e->seq==seq;
}
