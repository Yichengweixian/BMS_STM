# 基础程序烧录工作卡（2026-10-30）

mode: exploratory
status: complete
verdict: null
evidence_scope: [build, bench, release_boot]

用户要求将当前基础源码烧录成功。未修改应用源码。

发现与处理：Keil 缺少 MX25UM25645G_ATK-CNN647B.FLM，已从用户配套压缩包安装至 D:/K5/ARM/Flash。工程仍保存另一只 ST-Link 序列号；本次 CubeProgrammer 显式指定实物序列号。用户切换 BOOT1=1、BOOT0=0 并重新上电后芯片连接恢复，无需升级 ST-Link。

构建：Arm Compiler 6.24，BMS_EX_Release，0 Error(s), 0 Warning(s)。镜像身份见 result.json。

烧录：HotPlug 方式首次擦除失败，保留失败日志；改为 SWD 100 kHz、Under Reset、Hardware reset，应用区写入并读回校验成功。没有执行全片擦除或写入预编译固件。原 0x70000000 引导区首字读取为 0x324D5453，仅证明存在镜像头。

启动确认：最初用户报告黑屏，实测 PC=0x18003514、VTOR=0x18000000、BOOTSR=0x3，说明实际仍是开发模式。用户将两个 BOOT 开关换到另一端并复位后确认 OLED 显示 BMS_EX。此为用户观察的 Flash 复位启动成功；最终纠正开关后的再次完全断电启动未单独观察。测量/功率级未验收。

