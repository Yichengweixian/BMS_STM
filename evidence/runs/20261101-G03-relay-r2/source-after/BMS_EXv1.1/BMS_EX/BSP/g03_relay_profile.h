#ifndef G03_RELAY_PROFILE_H
#define G03_RELAY_PROFILE_H
/* Frozen exploratory raw-code envelope, derived from board-rehearsal-01.
 * NOT manufacturer cell limits or calibrated absolute-current protection.
 * 38865..38872 cell codes observed; stop on a 500-code (~50 mV nominal)
 * departure from that measured envelope. GPIO1 baseline 8994..9006,
 * with 36-code (3x observed peak-to-peak) drift margin fixed before live. */
#ifndef G3R_LIVE_PROFILE_VERIFIED
#define G3R_LIVE_PROFILE_VERIFIED 1U
#endif
#ifndef G3R_CELL_LOW_CODE
#define G3R_CELL_LOW_CODE 38365U
#endif
#ifndef G3R_CELL_HIGH_CODE
#define G3R_CELL_HIGH_CODE 39372U
#endif
#define G3R_BASE_LOW_CODE 8958U
#define G3R_BASE_HIGH_CODE 9042U
#define G3R_PROFILE_ID "relay-exploration-20261101-r2"
#define G3R_FIRMWARE "g03-relay-r2"
#endif
