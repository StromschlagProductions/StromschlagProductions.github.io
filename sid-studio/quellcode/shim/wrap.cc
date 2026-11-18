#include "../resid/sid.h"
using namespace reSID;
static SID* chips[8];
static short outbuf[8][4096];
extern "C" {
int hb_init(int n, int model, double clock, double rate, int method){
  for(int i=0;i<n && i<8;i++){ chips[i]=new SID(); chips[i]->set_chip_model(model?MOS8580:MOS6581);
    chips[i]->set_sampling_parameters(clock, method==2?SAMPLE_RESAMPLE:(method==1?SAMPLE_INTERPOLATE:SAMPLE_FAST), rate); chips[i]->reset(); }
  return n; }
void hb_write(int i,int reg,int val){ chips[i]->write(reg,val); }
void hb_reset(int i){ chips[i]->reset(); }
/* clocks chip i for `cycles` cycles, writes up to n samples into its buffer, returns sample count */
int hb_clock(int i,int cycles,int n){ cycle_count dt=cycles; return chips[i]->clock(dt, outbuf[i], n, 1); }
short* hb_buf(int i){ return outbuf[i]; }
void hb_bias(int i,double v){ chips[i]->adjust_filter_bias(v); }
}
