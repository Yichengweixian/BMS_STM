# G01/G02补测与G03首次单次继电器实验工作卡

日期：2026-11-01。status=complete（本轮任务），verdict=pass（仅首次通路响应并恢复），evidence_scope=static/build/simulation/bench。G01/G02/G03完整阶段验收仍为未判定。

本轮已完成无需现场仪器操作的G01/G02补测、独立单次状态机与主机工具、Debug/Release构建、烧录读回、r2正常BOOT身份及禁能演练，并执行一次真实PG5动作。结果为**观察到响应并恢复**：窗口内4组完整样本，AFE约下降2493码，撤销后回带；PG5命令窗口98.528565ms，最终输出0、故障0、live_used=1。没有PWM、PI或自动重试。

|交付|入口|
|---|---|
|首次实验结果与边界|[首次实验报告](first-experiment-report.md)|
|G01/G02补测与缺项|[补测结果表](retest-matrix.md)|
|冻结条件与停止办法|[工况表](conditions-table.md)、[原始冻结JSON](conditions-frozen.json)、[就绪证据](conditions-ready.json)|
|固件、源码和构建日志|[镜像哈希](artifact-manifest.json)、firmware/、source-after/、delivery-manifest.json|
|主机工具|[relay_capture.py](../../../scripts/g03/relay_capture.py)、[接口说明](../../../instructions/specs/G03-relay-single.md)|
|真实原始数据/派生CSV/时间曲线/停止|[live-01](live-01/manifest.json)、[曲线](live-01/response.png)、[派生清单](live-01/derived/manifest.json)|
|禁能数据|[board-rehearsal-01](board-rehearsal-01/result.json)|
|结束后状态及常规采集|[最终查询](final-status-01/result.json)、[G01恢复分析](g01-recovery-analysis.json)|

Release SHA256 `8ff78e03997c4a5facd8f6feade09024fdd4721a3f0e32fc3531312bf1598c49`；Debug/Release都完成构建，Debug仅原有EXTRAM警告。首次r1下载失败与r2首次测试夹具失败原样保留；未覆盖原始运行结果。最终状态保留完成锁存，重连只查询/读取；下一步完整G03 PWM开环需单独安排，不属于本轮自动续跑范围。
