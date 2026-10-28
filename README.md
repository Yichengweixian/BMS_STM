# STM32N6 BMS 综合实验

本项目围绕三节电池的电压/电流/温度测量、双向DC-DC恒流控制、串口交互与SOC数据/模型部署。当前源码仍处于基础模板阶段，硬件验收尚未执行。

## 从这里进入

- **执行规范**：[instructions/README.md](instructions/README.md)；当前进度：[STATUS](instructions/STATUS.md)。
- **系统解释与验收路线**：[BMS实施与验收指南](instructions/BMS实施与验收指南.html)。
- **硬件、软件与PI原理**：[BMS系统原理与开发路线](docs/guides/BMS系统原理与开发路线.html)。
- **每个文件的用途**：[目录逐文件说明](docs/guides/目录逐文件说明.html)。
- **代理入口**：[AGENTS.md](AGENTS.md)，已指向本项目的BMS规范。
- **Keil工程**：[BMS_EX_Appli.uvprojx](BMS_EXv1.1/BMS_EX/MDK-ARM/Appli/BMS_EX_Appli.uvprojx)。

## 目录分工

```text
综合实验/
├─ AGENTS.md                     项目代理执行入口
├─ README.md                     本导航
├─ BMS_EXv1.1/BMS_EX/             原Keil工程；目录与文件内容保持原样
├─ instructions/                 BMS流程、验收标准、状态和记录模板
│  ├─ specs/                     测量、验收、数据与硬件profile
│  ├─ templates/                 工作卡、运行manifest、标定记录
│  ├─ references/                来源、哈希、迁移记录与历史快照
│  └─ validation/                文档生成/检查脚本与报告
├─ docs/
│  ├─ course/                    PPT与任务2实验步骤
│  ├─ manuals/                   工程模板、上位机、安装手册
│  └─ guides/                    原理指南与逐文件说明HTML
├─ firmware/prebuilt/            配套现成HEX；与模板源码单独管理
└─ tools/
   ├─ host/                      BMS上位机ZIP
   ├─ flash-loaders/              三个MX25外部Flash算法/加载器RAR
   └─ installers/                STM32CubeProgrammer安装ZIP
```

将来正式实验使用 `evidence/runs/<run_id>/` 保存raw、derived和结果；当前没有创建空实验或虚构运行记录。

## 本次整理范围

2026-10-28：将原根目录资料、工具与预编译固件按用途归类；`BMS执行规范` 改为 `instructions`；同步入口、网页链接和来源清单。Keil工程保持原路径，未删除其备份、临时文件或旧产物，未解压、安装或运行工具。

原始文件的移动关系与SHA-256见 [layout-migration.json](instructions/references/layout-migration.json)。文档及源清单的旧版保存在 `instructions/references/history/`；它们反映历史目录，不是当前入口。Office生成的 `~$` 临时锁文件保留由Office管理。

流程已采用，但E类验收数值仍需在正式实验前固定，H类实物参数仍待确认。下一阶段仍是G00基线与G01测量链准备，目录整理不构成固件或硬件通过。

## GitHub 同步与获取

目标仓库：[Yichengweixian/BMS_STM](https://github.com/Yichengweixian/BMS_STM)。源码、课程资料、执行规范、阅读指南、配套HEX和工具压缩包纳入版本管理；ZIP/RAR通过Git LFS保存。

```sh
git lfs install
git clone https://github.com/Yichengweixian/BMS_STM.git
cd BMS_STM
git lfs pull
```

GitHub网页中的HTML通常显示源码，克隆后用浏览器打开即可阅读。只下载普通源码ZIP可能没有完整LFS内容；以Git LFS获取工具包。

`.gitignore`排除Office锁文件、临时/备份、个人Keil界面配置、`.workbuddy`本地记录和可再生成的编译输出，原文件仍留在本机。`firmware/prebuilt/BMS_Appli.hex`单独保留。

`instructions/references/history`与目录迁移报告记录原机器上的历史状态，可能引用本机路径、外部参考目录及未上传的缓存；它们不是新克隆环境的构建或硬件通过证明。正式基线仍需按G00重新建立。
