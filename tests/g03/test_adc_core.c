#include "g03_adc_core.h"
#include "nominal_current.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>
int main(void)
{
    G3ACore c={0};G3AEvent e;uint32_t low=99,high=99,t,i;
    /* Independent vectors from HEX literal values, including mismatch baseline. */
    assert(fabs(Current_McuNominal(1008,.9f)-(-.60618466))<.000002);
    assert(fabs(Current_AfeNominal(9000,.9f))<.000001);
    assert(G3A_CurrentUA(2048,2048000)==0);
    assert(abs(G3A_CurrentUA(2148,2048000)-58315)<2);
    assert(G3A_Window(2048000,50,&low,&high));assert(low==1963&&high==2133);
    assert(!G3A_Window(1008000,1000,&low,&high));assert(low==1963&&high==2133);
    assert(!G3A_Window(0,50,&low,&high));assert(!G3A_Window(2048000,0,&low,&high));
    assert(!G3A_Start(&c,1000,0,0,0));assert(G3A_Configure(&c,2048000,50));
    assert(!G3A_Configure(&c,1008000,1000));assert(c.zero_mcode==2048000);
    assert(G3A_Start(&c,1000,0xfffffe00U,0,0));
    for(i=1;i<=1000;++i){t=0xfffffe00U+i;G3A_Sample(&c,2048,0,t,i*100U);
        if(i%200==0)assert(G3A_Heartbeat(&c,t,i*100U));
        G3A_Tick(&c,t,i*100U);}
    assert(c.state==G3A_IDLE&&c.reason==1&&c.count==1000&&c.step==4&&c.overwritten==0);
    assert(G3A_Read(&c,0,&e)&&e.event==G3A_START);assert(!G3A_Read(&c,c.written,&e));
    assert(G3A_Start(&c,1000,0,0,0));G3A_Sample(&c,2134,0,1,100);
    assert(c.faults&G3A_CURRENT);assert(!c.ccr&&c.trip_cycles==100);
    assert(!G3A_Start(&c,1000,0,0,0));assert(G3A_Clear(&c));assert(!c.configured);
    for(i=0;i<5;i++){
        assert(G3A_Configure(&c,2048000,50));assert(G3A_Start(&c,2000,0,0,0));
        if(i==0)G3A_Sample(&c,0,0,1,100);
        if(i==1)G3A_Sample(&c,2048,G3A_OVR,1,100);
        if(i==2)G3A_Sample(&c,2048,G3A_AWD,1,100);
        if(i==3)G3A_Tick(&c,6,100);
        if(i==4){for(t=1;t<=800;t++){G3A_Sample(&c,2048,0,t,t);G3A_Tick(&c,t,t);}}
        assert(c.state==G3A_FAULT&&c.faults);assert(G3A_Clear(&c));
    }
    assert(G3A_Configure(&c,2048000,50));assert(G3A_Start(&c,2000,0,0,0));
    for(i=0;i<3000;i++)G3A_Sample(&c,2048,0,1,i);
    assert(c.overwritten>0);assert(!G3A_Read(&c,0,&e));assert(G3A_Read(&c,c.overwritten,&e));
    puts("PASS: HEX vectors, conservative window/no rail clamp, sweep, rollover, faults, trace retention");return 0;
}
