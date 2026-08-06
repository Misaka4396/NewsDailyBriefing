# NewsDailyBriefing — 全球每日新闻日报推送器

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![UI: tkinter/ttkbootstrap](https://img.shields.io/badge/UI-tkinter%2Fttkbootstrap-teal.svg)]()

自动化 **每日新闻 + 汇率日报** 推送系统：抓取多源全球新闻与货币汇率，生成精美 HTML 日报，
通过 SMTP 定时推送到指定邮箱。内置 Windows 桌面 GUI（支持系统托盘驻留）与定时调度器。

> ⚠️ 本项目仅供个人学习研究使用。

---

## 目录

- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [命令行/打包](#命令行打包)
- [项目结构](#项目结构)
- [修改日志](#修改日志)
- [License](#license)

---

## 功能特性

| 特性 | 说明 |
|------|------|
| 📰 多源新闻抓取 | 聚合全球新闻源，支持缓存，降低重复请求 |
| 💱 货币汇率 | 自动获取多币种最新汇率 |
| 📧 HTML 日报 | 生成格式化 HTML 日报，SMTP 邮件推送 |
| ⏰ 定时任务 | 内置调度器，每日定时自动生成并发送 |
| 🖥️ 桌面 GUI | tkinter + ttkbootstrap 现代风格，国家/货币多选、预览、发送 |
| 🗔 系统托盘 | 最小化到托盘驻留，托盘菜单快捷操作 |
| 🔐 配置加密 | cryptography 加密存储邮箱授权码 |
| 📄 日志系统 | 双路日志（文件 + GUI 日志窗口），SMTP 诊断信息完善 |

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

### 打包为 EXE

```bash
build.bat
# 或
pyinstaller NewsDailyBriefing.spec --noconfirm
```

## 命令行/打包

| 命令 | 说明 |
|------|------|
| `python main.py` | 启动桌面 GUI |
| `build.bat` | 一键打包 exe |
| `python generate_icon.py` | 重新生成应用图标 |

## 项目结构

```
NewsDailyBriefing/
├── main.py               # GUI 主程序入口
├── config.py             # 配置加载/保存（国家/货币/邮箱）
├── news_fetcher.py       # 新闻抓取器
├── currency_fetcher.py   # 汇率抓取器
├── report_generator.py   # HTML 日报生成
├── email_sender.py       # SMTP 邮件发送（重试/诊断）
├── scheduler.py          # 每日定时调度器
├── tray_manager.py       # 系统托盘
├── logger.py             # 日志模块
├── generate_icon.py      # 图标生成脚本
├── build.bat             # 打包脚本
└── requirements.txt
```

## 修改日志

详见 [CHANGELOG.md](CHANGELOG.md)。

## License

MIT License — 详见 [LICENSE](LICENSE)