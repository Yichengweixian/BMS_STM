#ifndef G03_ADC_CORE_H
#define G03_ADC_CORE_H
#include <stdint.h>
#define G3A_TRACE_SIZE 256U
enum { G3A_IDLE, G3A_RUNNING, G3A_FAULT };
enum { G3A_RANGE=1U, G3A_OVR=2U, G3A_STALE=4U, G3A_LINK=8U,
       G3A_INTERLOCK=16U, G3A_AWD=32U, G3A_CURRENT=64U, G3A_ADC=128U };
enum { G3A_SAMPLE=1U, G3A_START=2U, G3A_STEP=3U, G3A_STOP=4U, G3A_TRIP=5U };
typedef struct {
    uint32_t seq,ms,cycles,raw; int32_t ua;
    uint32_t ccr,event,faults;
} G3AEvent;
typedef struct {
    uint32_t state,faults,reason,start_ms,last_ms,heartbeat_ms,duration_ms;
    uint32_t count,raw,ccr,step,low,high,zero_mcode,limit_ma,configured;
    uint32_t written,overwritten,trip_ms,trip_cycles,probe;
    int32_t ua;
    G3AEvent trace[G3A_TRACE_SIZE];
} G3ACore;
int32_t G3A_CurrentUA(uint32_t raw,uint32_t zero_mcode);
int G3A_Window(uint32_t zero_mcode,uint32_t limit_ma,uint32_t *low,uint32_t *high);
int G3A_Configure(G3ACore *c,uint32_t zero_mcode,uint32_t limit_ma);
int G3A_Start(G3ACore *c,uint32_t duration,uint32_t now,uint32_t cycles,uint32_t probe);
void G3A_Sample(G3ACore *c,uint32_t raw,uint32_t flags,uint32_t now,uint32_t cycles);
void G3A_Tick(G3ACore *c,uint32_t now,uint32_t cycles);
void G3A_Trip(G3ACore *c,uint32_t fault,uint32_t now,uint32_t cycles);
void G3A_Stop(G3ACore *c,uint32_t now,uint32_t cycles,uint32_t reason);
int G3A_Heartbeat(G3ACore *c,uint32_t now,uint32_t cycles);
int G3A_Clear(G3ACore *c);
int G3A_Read(const G3ACore *c,uint32_t seq,G3AEvent *e);
#endif
