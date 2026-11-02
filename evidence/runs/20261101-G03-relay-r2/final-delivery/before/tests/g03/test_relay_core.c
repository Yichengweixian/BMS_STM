#include "g03_relay_core.h"
#include <assert.h>
#include <stdio.h>
static G3RCore c;
static uint16_t raw[4]={38900,38910,38920,9000};
static uint32_t baseline(uint32_t start,uint32_t live)
{
    unsigned i;G3R_Init(&c);assert(G3R_Begin(&c,live,start,36000,41000));G3R_Ready(&c,start);
    for(i=0;i<G3R_BASE_SAMPLES;++i)G3R_Sample(&c,start+i*20U,start+i*20U,1,raw);
    assert(c.state==G3R_PULSE && c.command_on && c.base_count==50U);return c.on_ms;
}
int main(void)
{
    uint32_t t;unsigned i;
    t=baseline(0,0);assert(!G3R_Begin(&c,1,t,36000,41000));
    assert(!G3R_Clear(&c));
    for(i=20;i<99;i+=20){G3R_Sample(&c,t+i,t+i,1,raw);G3R_Tick(&c,t+i);assert(c.command_on);}
    G3R_Tick(&c,t+99);assert(c.state==G3R_POST && !c.command_on && c.reason==G3R_END_DEADLINE);
    for(i=0;i<5;++i)G3R_Sample(&c,t+100+i*20,t+100+i*20,1,raw);
    assert(c.recover_count==5);G3R_Tick(&c,t+1099);assert(c.state==G3R_DONE);assert(G3R_Clear(&c));
    t=baseline(0xfffffc00U,1);G3R_Stop(&c,t+10);assert(!c.command_on && c.reason==G3R_END_STOP);
    G3R_Stop(&c,t+20);assert(c.off_ms==t+10);G3R_Tick(&c,t+1010);assert(c.state==G3R_DONE);
    t=baseline(0,1);G3R_Tick(&c,t+41);assert(c.faults&G3R_STALE);assert(!c.command_on);
    t=baseline(0,1);G3R_Sample(&c,t+1,t+1,0,raw);assert(c.faults&G3R_DATA);
    t=baseline(0,1);G3R_Sample(&c,t+1,t-50,1,raw);assert(c.faults&G3R_STALE);
    t=baseline(0,1);raw[1]=35999;G3R_Sample(&c,t+1,t+1,1,raw);assert(c.faults&G3R_CELL);raw[1]=38910;
    t=baseline(0,0);c.samples=G3R_CAPACITY;G3R_Sample(&c,t+1,t+1,1,raw);assert(c.faults&G3R_BUFFER);
    t=baseline(0,0);G3R_Trip(&c,G3R_CPU,t+1);G3R_Trip(&c,G3R_DATA,t+50);assert(c.post_start==t+1);
    G3R_Tick(&c,t+1001);assert(c.state==G3R_FAULT);
    G3R_Init(&c);assert(!G3R_Begin(&c,1,0,0,0));assert(G3R_Begin(&c,0,0,0,0));
    G3R_Tick(&c,201);assert(c.faults&G3R_DATA);
    G3R_Init(&c);assert(G3R_Begin(&c,0,0,0,0));G3R_Ready(&c,0);
    for(i=0;i<50;++i){raw[3]=(uint16_t)(9000+i*3);G3R_Sample(&c,i*20,i*20,1,raw);}
    assert(c.faults&G3R_BASE);raw[3]=9000;
    puts("PASS relay core deadlines, wrap, stale/error/cell/buffer, stop and latch");return 0;
}
