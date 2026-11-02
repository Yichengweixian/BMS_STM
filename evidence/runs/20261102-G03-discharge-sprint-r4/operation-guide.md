# 现场操作步骤（r4放电）

使用本目录r4 Release HEX，运行身份g03-power-points-r4，SHA256 d24854613869c973c3483ebc7ca7d973fb5bf2ca67e75ca8789ff454b5703784。原始实测文件不要作为下一次输出目录，必须建立新目录。

1. 接线前电源OFF。真实电池取出；CH1→左A、CH2→中B、CH3→右C，各路红到本座＋、黑到本座－，各黑端不互连。检查CH1/A接触牢固。本板已实测映射A=cell13、B=cell7、C=cell1。
2. 三路独立模式，各3.500V、CC0.600A、OCP0.550A启用、OVP3.650V启用。绿色接牢33Ω负载，黄色口空。18V原辅助电源保留。DMM6500选Front DCV100V，红线INPUT HI、黑线INPUT LO，跨负载两端，SENSE/AMPS孔不用。
3. 烧录仅在三路OFF且BOOT1=1/BOOT0=0、RESET后进行，读回核验；正常运行恢复BOOT1=0/BOOT0=0并RESET。固件默认关闭，不自动续跑。打开三路，确认各路约3.5V、空闲电流近0、无CC/保护提示。
4. 用scripts/g03/power_capture.py的query模式核对身份、used0、faults0、owned0、bits0。启动只接受四个固定profile：0x50393301 D0.90/100ms、0x50393302 D0.80/100ms、0x50393303 D0.90/2s、0x50393304 D0.80/2s。D与时长不能在运行中修改；不自动扫点。
5. 每次实际启动前核对工况，独立保存与当前镜像/profile匹配的contract和新run目录。沿用本次接线及保护范围时，现场可选择已验证的D0.90/2s观察10.9V附近，或D0.80/2s观察12.15V附近；数值是本次记录参考，不是对不同负载/供能的保证。需先核对短点或已有同条件短点证据，不跳过默认关闭检查。
6. 主机启动命令为 `power_capture.py --port COM12 --mode live --profile <冻结ID> --contract <本次contract.json> --out <全新run目录> --image <r4 HEX路径> --sha256 d24854613869c973c3483ebc7ca7d973fb5bf2ca67e75ca8789ff454b5703784`。安装环境中的Python需有pyserial；本机可用Codex缓存Python和本次vendor路径，见脚本依赖说明。端口重插后如变化，先核对设备，不盲发命令。
7. 2秒窗期间观察DMM和电源，自动记录1秒前后数据。需要提前STOP时，当前前台采集进程按Ctrl+C：交付版主机发送一次op43 STOP并保存结果；这条主机中断路径通过离线测试，尚无新带载时延验收。即使主机失联，2秒点保留200ms心跳退出和本地总时限。出现CC/跳闸/异常气味等，立即三路OFF，保留失败，不重开重试。
8. 正常完成应faults0、bits0、owned0、restored1、used1；CSV保留空缺、质量标志和跨窗样本。令牌已用时再次启动会被拒绝；下一独立点需有意RESET并重新核对关闭状态，故障后先排原因，不用RESET自动重试。全部结束三路OFF。

演示建议先打开[结果报告](report.md)说明两端口数值，再按上述步骤做一笔已冻结固定D记录。报告中的负载电流是33Ω标签换算，电池电流是AFE标称换算，不能说成同一电流或已完成精度验收。

本次采集所用主机原版在reproduction/scripts/g03/power_capture.py；交付主机追加了Ctrl+C发送STOP和自身源码哈希记录，固件未改变。无需重新烧录。源代码与镜像留在本工程，未提交修改、旧固件和失败run均保留。


## 本机直接运行入口

在PowerShell进入工程根目录后，仅查询（默认不会启动）：

```powershell
.\scripts\g03\run_demo.ps1 -Mode Query -Port COM12
```

按本文完成接线、供能和默认关闭确认，且当前未使用令牌时，执行一个D0.90/2s演示：

```powershell
.\scripts\g03\run_demo.ps1 -Mode Live -Point D90 -Port COM12 -BenchReady
```

D0.80使用`-Point D80`。`-BenchReady`表示操作者已核对本文工况，不能代替实际检查。脚本先查询并验证used/faults/owned/bits，再建立本次新contract与新目录；不会自动RESET、重试、改变阈值或连续扫点。当前实验结束时令牌已用，因此直接再次Live会拒绝，须按步骤有意RESET后重新核对。

该入口使用本机已有Codex缓存Python和本次pyserial vendor，路径写在脚本开头；复制到另一台电脑时需安装Python+pyserial并修改这两处路径。入口仅做语法核对，底层采集工具已完成本报告实物运行；没有在收工后再次发起功率测试。
