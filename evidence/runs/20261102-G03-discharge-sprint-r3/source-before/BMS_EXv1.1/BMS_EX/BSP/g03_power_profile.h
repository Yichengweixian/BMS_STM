#ifndef G03_POWER_PROFILE_H
#define G03_POWER_PROFILE_H
/* Generated/frozen alongside hardware-profile.json. Engineering exploration,
 * NOT component ratings. External source contract is required by the host.
 * PA1 is deliberately not used for current protection. */
#define G3P_PROFILE_ID 0x50393032U
#define G3P_CCR 1800U
#define G3P_ARR 2000U
#define G3P_RUN_US 100000U
#define G3P_PRE_US 1000000U
#define G3P_SETTLE_US 100000U
#define G3P_COAST_US 20000U
#define G3P_RECOVERY_US 1000000U
#define G3P_SAMPLE_US 20000U
#define G3P_STALE_US 40000U
#define G3P_CELL_START_LOW 34500U
#define G3P_CELL_START_HIGH 35500U
#define G3P_CELL_LOW 33000U
#define G3P_CELL_HIGH 36500U
#define G3P_DISCHARGE_MA 550
#define G3P_CHARGE_MA 50
#define G3P_PASSIVE_MIN_MA 200
#define G3P_PASSIVE_MAX_MA 450
#define G3P_ZERO_LOW 8900U
#define G3P_ZERO_HIGH 9100U
#define G3P_ZERO_SPAN 36U
#define G3P_CAPACITY 160U
#endif
