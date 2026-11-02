#include "g03_control.h"
#include <string.h>
static void state(G03Control *c, uint32_t next, uint32_t now)
{ if(c->state!=next){c->state=next;c->entered_ms=now;++c->transitions;} }
int G03_Active(const G03Control *c)
{ return c->initialized && c->state!=G03_STOPPED && c->state!=G03_FAULT; }
void G03_Init(G03Control *c)
{
    /* Only cold initialization may clear a fault. Repeated init fails closed. */
    if(c->initialized){G03_Fault(c,G03_F_EXTERNAL,c->entered_ms);return;}
    memset(c,0,sizeof *c);c->initialized=1U;c->ccr=1000U;
}
static int valid_config(const G03Config *p)
{
    return p && p->known==1U && p->break_ms>0U && p->relay_ms>0U && p->decay_ms>0U &&
        p->decay_ms<p->decay_timeout_ms && p->decay_timeout_ms<0x80000000U &&
        p->break_ms<0x80000000U && p->relay_ms<0x80000000U &&
        p->link_ms>0U && p->link_ms<0x80000000U && p->stale_ms>0U && p->stale_ms<0x80000000U &&
        p->max_run_ms>0U && p->max_run_ms<0x80000000U && p->ccr_min>0U &&
        p->ccr_min<=1000U && p->ccr_max>=1000U && p->ccr_max<2000U &&
        p->cell_min_mv>0 && p->cell_max_mv>p->cell_min_mv &&
        p->charge_max_ma>0 && p->discharge_max_ma>0 && p->temp_min_mc<p->temp_max_mc &&
        p->relay_release_ma>=0 && p->relay_release_ma<p->charge_max_ma && p->relay_release_ma<p->discharge_max_ma;
}
uint32_t G03_Configure(G03Control *c, const G03Config *cfg)
{
    if(!c->initialized)return G03_NOT_READY;
    if(c->state==G03_FAULT)return G03_FAULTED;
    if(c->state!=G03_STOPPED)return G03_BUSY;
    /* Invalid input does not replace a previous valid configuration. */
    if(!valid_config(cfg))return G03_BAD_ARGUMENT;
    c->cfg=*cfg;c->configured=1U;return G03_OK;
}
void G03_Fault(G03Control *c,uint32_t bits,uint32_t now)
{
    if(!c->initialized || !bits)return;
    c->shadow_pwm=0U;c->shadow_relays=0U;c->faults|=bits;
    c->reason=G03_REASON_FAULT;c->stop_ms=now;state(c,G03_FAULT,now);
}
static uint32_t check(const G03Control *c,const G03Sample *s,uint32_t now,uint32_t direction)
{
    uint32_t f=0U,i;
    if(!s || s->valid!=1U || s->calibrated!=1U)return G03_F_SENSOR;
    if((uint32_t)(now-s->at_ms)>c->cfg.stale_ms)return G03_F_STALE;
    for(i=0;i<3U;++i){if(s->cell_mv[i]<c->cfg.cell_min_mv)f|=G03_F_UV;if(s->cell_mv[i]>c->cfg.cell_max_mv)f|=G03_F_OV;}
    if(s->current_ma>c->cfg.charge_max_ma || s->current_ma< -c->cfg.discharge_max_ma)f|=G03_F_CURRENT;
    if((direction==1U && s->current_ma< -c->cfg.relay_release_ma) ||
       (direction==2U && s->current_ma>c->cfg.relay_release_ma))f|=G03_F_REVERSE;
    if(s->temp_mc<c->cfg.temp_min_mc || s->temp_mc>c->cfg.temp_max_mc)f|=G03_F_TEMP;
    return f;
}
uint32_t G03_Start(G03Control *c,uint32_t direction,uint32_t duration_ms,uint32_t now,const G03Sample *s)
{
    uint32_t f;
    if(!c->initialized || !c->configured)return G03_NOT_READY;
    if(c->faults)return G03_FAULTED;
    if(c->state!=G03_STOPPED)return G03_BUSY; /* No queued reversal/restart. */
    if((direction!=1U && direction!=2U) || !duration_ms || duration_ms>c->cfg.max_run_ms)return G03_BAD_ARGUMENT;
    f=check(c,s,now,0U);
    if(f){G03_Fault(c,f,now);return G03_FAULTED;}
    if(s->current_ma>c->cfg.relay_release_ma || s->current_ma< -c->cfg.relay_release_ma)return G03_NOT_READY;
    c->direction=direction;c->duration_ms=duration_ms;c->start_ms=now;c->stop_ms=0U;
    c->heartbeat_ms=now;c->reason=G03_REASON_NONE;c->shadow_pwm=0U;c->shadow_relays=0U;
    ++c->starts;state(c,G03_BREAK_WAIT,now);return G03_OK;
}
uint32_t G03_Compare(G03Control *c,uint32_t ccr)
{
    if(!c->initialized || !c->configured)return G03_NOT_READY;
    if(c->faults)return G03_FAULTED;
    if(ccr<c->cfg.ccr_min || ccr>c->cfg.ccr_max)return G03_BAD_ARGUMENT;
    if(c->state!=G03_STOPPED && c->state!=G03_CHARGE && c->state!=G03_DISCHARGE)return G03_BUSY;
    c->ccr=ccr;return G03_OK;
}
void G03_Stop(G03Control *c,uint32_t now,uint32_t reason)
{
    if(!c->initialized)return;
    c->shadow_pwm=0U;
    if(c->state==G03_FAULT || c->state==G03_STOPPED || c->state==G03_DECAY_WAIT)return;
    c->reason=reason;c->stop_ms=now;
    if(!c->shadow_relays)state(c,G03_STOPPED,now);
    else state(c,G03_DECAY_WAIT,now);
}
uint32_t G03_Clear(G03Control *c)
{
    if(!c->initialized)return G03_NOT_READY;
    if(G03_Active(c))return G03_BUSY;
    c->shadow_pwm=0U;c->shadow_relays=0U;c->faults=0U;c->reason=G03_REASON_NONE;
    state(c,G03_STOPPED,c->stop_ms);return G03_OK;
}
uint32_t G03_Heartbeat(G03Control *c,uint32_t now)
{
    if(!G03_Active(c))return c->faults?G03_FAULTED:G03_NOT_READY;
    if((uint32_t)(now-c->heartbeat_ms)>=c->cfg.link_ms){G03_Fault(c,G03_F_LINK,now);return G03_FAULTED;}
    c->heartbeat_ms=now;return G03_OK;
}
void G03_Tick(G03Control *c,uint32_t now,const G03Sample *s,uint32_t interlock_bad)
{
    uint32_t f,elapsed;
    if(!G03_Active(c))return;
    f=check(c,s,now,c->direction);
    if(interlock_bad || c->shadow_relays==3U ||
       (c->shadow_pwm && c->shadow_relays!=c->direction))f|=G03_F_INTERLOCK;
    if((uint32_t)(now-c->heartbeat_ms)>=c->cfg.link_ms)f|=G03_F_LINK;
    if(f){G03_Fault(c,f,now);return;}
    if(c->state!=G03_DECAY_WAIT && (uint32_t)(now-c->start_ms)>=c->duration_ms)
        G03_Stop(c,now,G03_REASON_DURATION);
    elapsed=now-c->entered_ms;
    if(c->state==G03_BREAK_WAIT && elapsed>=c->cfg.break_ms){
        c->shadow_relays=c->direction;state(c,G03_RELAY_WAIT,now);
    }else if(c->state==G03_RELAY_WAIT && elapsed>=c->cfg.relay_ms){
        c->shadow_pwm=1U;state(c,c->direction==1U?G03_CHARGE:G03_DISCHARGE,now);
    }else if(c->state==G03_DECAY_WAIT){
        if(elapsed>=c->cfg.decay_ms && s->current_ma<=c->cfg.relay_release_ma && s->current_ma>= -c->cfg.relay_release_ma){
            c->shadow_relays=0U;state(c,G03_STOPPED,now);
        }else if(elapsed>=c->cfg.decay_timeout_ms)G03_Fault(c,G03_F_DECAY,now);
    }
}
