#ifndef G03_RELAY_PROFILE_H
#define G03_RELAY_PROFILE_H
/* Live gate remains closed until a run-specific evidence-backed profile exists.
 * Zero is absence of a limit, never a physical rating or acceptable cell value. */
#ifndef G3R_LIVE_PROFILE_VERIFIED
#define G3R_LIVE_PROFILE_VERIFIED 0U
#endif
#ifndef G3R_CELL_LOW_CODE
#define G3R_CELL_LOW_CODE 0U
#endif
#ifndef G3R_CELL_HIGH_CODE
#define G3R_CELL_HIGH_CODE 0U
#endif
#define G3R_PROFILE_ID "relay-observation-draft-v1"
#define G3R_FIRMWARE "g03-relay-r1"
#endif
