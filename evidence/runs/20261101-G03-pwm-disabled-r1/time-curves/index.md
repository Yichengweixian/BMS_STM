# 单次PWM禁能：逐次曲线与停止事件

15个已完成场景各有独立曲线；原软件复位失败记录不生成虚假采样图。全部输出位为0，原码未物理标定；无fast样本时不补零。

|场景|时间曲线|该次停止事件|
|---|---|---|
|board-suite-01/01-normal|[曲线](board-suite-01-01-normal.png)|[事件](../board-suite-01/01-normal/derived/stop-events.csv)|
|board-suite-01/02-sample-6p5|[曲线](board-suite-01-02-sample-6p5.png)|[事件](../board-suite-01/02-sample-6p5/derived/stop-events.csv)|
|board-suite-01/03-adc-stale|[曲线](board-suite-01-03-adc-stale.png)|[事件](../board-suite-01/03-adc-stale/derived/stop-events.csv)|
|board-suite-01/04-adc-invalid|[曲线](board-suite-01-04-adc-invalid.png)|[事件](../board-suite-01/04-adc-invalid/derived/stop-events.csv)|
|board-suite-01/05-fifo-overrun|[曲线](board-suite-01-05-fifo-overrun.png)|[事件](../board-suite-01/05-fifo-overrun/derived/stop-events.csv)|
|board-suite-01/06-awd-low|[曲线](board-suite-01-06-awd-low.png)|[事件](../board-suite-01/06-awd-low/derived/stop-events.csv)|
|board-suite-01/07-awd-high|[曲线](board-suite-01-07-awd-high.png)|[事件](../board-suite-01/07-awd-high/derived/stop-events.csv)|
|board-suite-02/01-cache-full|[曲线](board-suite-02-01-cache-full.png)|[事件](../board-suite-02/01-cache-full/derived/stop-events.csv)|
|board-suite-02/02-heartbeat-expiry|[曲线](board-suite-02-02-heartbeat-expiry.png)|[事件](../board-suite-02/02-heartbeat-expiry/derived/stop-events.csv)|
|board-suite-02/03-explicit-stop|[曲线](board-suite-02-03-explicit-stop.png)|[事件](../board-suite-02/03-explicit-stop/derived/stop-events.csv)|
|board-suite-02/04-foreground-stall|[曲线](board-suite-02-04-foreground-stall.png)|[事件](../board-suite-02/04-foreground-stall/derived/stop-events.csv)|
|board-suite-02/05-bad-crc|[曲线](board-suite-02-05-bad-crc.png)|[事件](../board-suite-02/05-bad-crc/derived/stop-events.csv)|
|board-suite-02/06-rx-pressure|[曲线](board-suite-02-06-rx-pressure.png)|[事件](../board-suite-02/06-rx-pressure/derived/stop-events.csv)|
|board-suite-02/07-duplicate-start|[曲线](board-suite-02-07-duplicate-start.png)|[事件](../board-suite-02/07-duplicate-start/derived/stop-events.csv)|
|board-suite-02/08-conflicting-start|[曲线](board-suite-02-08-conflicting-start.png)|[事件](../board-suite-02/08-conflicting-start/derived/stop-events.csv)|
