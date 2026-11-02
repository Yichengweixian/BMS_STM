#include "g03_relay_core.h"
#include <string.h>
int G3R_Active(const G3RCore *c)
{return c->state>=G3R_PREPARE && c->state<=G3R_POST;}
void G3R_Init(G3RCore *c){memset(c,0,sizeof *c);}
int G3R_Begin(G3RCore *c,uint32_t live,uint32_t now,uint32_t low,uint32_t high)
{
    if(c->state!=G3R_IDLE || live>1U || (live && (!low||low>=high||high>=65535U)))return 0;
    G3R_Init(c);c->live=live;c->cell_low=low;c->cell_high=high;
    c->state=G3R_PREPARE;c->session_start=now;c->last_sample=now;c->base_min=65535U;return 1;
}
void G3R_Ready(G3RCore *c,uint32_t now)
{if(c->state==G3R_PREPARE){c->state=G3R_BASELINE;c->last_sample=now;}}
static void finish_pulse(G3RCore *c,uint32_t now,uint32_t reason)
{
    if(c->state!=G3R_POST){c->off_ms=now;c->post_start=now;c->state=G3R_POST;}
    c->command_on=0;c->reason=reason;
}
void G3R_Trip(G3RCore *c,uint32_t fault,uint32_t now)
{
    if(!G3R_Active(c))return;
    c->faults|=fault;finish_pulse(c,now,G3R_END_FAULT);
}
void G3R_Stop(G3RCore *c,uint32_t now)
{if(G3R_Active(c))finish_pulse(c,now,c->faults?G3R_END_FAULT:G3R_END_STOP);}
void G3R_Tick(G3RCore *c,uint32_t now)
{
    if(!G3R_Active(c))return;
    if(c->state==G3R_PREPARE){
        if((uint32_t)(now-c->session_start)>200U)G3R_Trip(c,G3R_DATA,now);
        return;
    }
    if(c->state==G3R_PULSE && (uint32_t)(now-c->on_ms)>=G3R_PULSE_MS)
        finish_pulse(c,now,G3R_END_DEADLINE);
    if(c->state==G3R_BASELINE || c->state==G3R_PULSE){
        if((uint32_t)(now-c->last_sample)>G3R_STALE_MS)G3R_Trip(c,G3R_STALE,now);
    }
    if(c->state==G3R_POST && (uint32_t)(now-c->post_start)>=G3R_POST_MS)
        c->state=c->faults?G3R_FAULT:G3R_DONE;
}
void G3R_Sample(G3RCore *c,uint32_t now,uint32_t oldest,uint32_t valid,const uint16_t raw[4])
{
    uint32_t i,delta;
    if(!G3R_Active(c)||c->state==G3R_PREPARE)return;
    ++c->samples;
    if(c->samples>G3R_CAPACITY){G3R_Trip(c,G3R_BUFFER,now);return;}
    if(!valid){c->recover_count=0;G3R_Trip(c,G3R_DATA,now);return;}
    if((uint32_t)(now-oldest)>G3R_STALE_MS){c->recover_count=0;G3R_Trip(c,G3R_STALE,now);return;}
    c->last_sample=oldest;
    for(i=0;i<3U;++i)if(c->live && (raw[i]<c->cell_low||raw[i]>c->cell_high)){
        G3R_Trip(c,G3R_CELL,now);return;
    }
    if(c->state==G3R_BASELINE){
        if(raw[3]<c->base_min)c->base_min=raw[3];
        if(raw[3]>c->base_max)c->base_max=raw[3];
        c->base_sum+=raw[3];++c->base_count;
        if(c->base_count==G3R_BASE_SAMPLES){
            if(c->base_max-c->base_min>100U){G3R_Trip(c,G3R_BASE,now);return;}
            c->center=(c->base_sum+G3R_BASE_SAMPLES/2U)/G3R_BASE_SAMPLES;
            c->tolerance=3U*(c->base_max-c->base_min);
            if(c->tolerance<20U)c->tolerance=20U;
            c->on_ms=now;c->state=G3R_PULSE;c->command_on=1U;
        }
    }else if(c->state==G3R_POST){
        delta=raw[3]>c->center?raw[3]-c->center:c->center-raw[3];
        c->recover_count=delta<=c->tolerance?c->recover_count+1U:0U;
    }
}
int G3R_Clear(G3RCore *c)
{if(G3R_Active(c))return 0;G3R_Init(c);return 1;}
