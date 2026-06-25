# ModelDownloader — 大模型下载工具

 <img width="15%" align="center" src="src\icon\HuggingScope.png" alt="logo">
 
一款基于 PySide6 + QFluentWidgets 构建的桌面大模型下载工具，支持从 Hugging Face 和 ModelScope 下载模型与数据集。

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 功能特性

- **双源支持** — 同时支持 Hugging Face 和 ModelScope 两个主流 AI 模型平台
- **树形文件选择** — 按目录结构展示仓库文件，支持多选/全选
- **下载队列管理** — 多任务排队下载，支持暂停/恢复/取消，最多 3 个并发
- **下载历史记录** — 持久化存储历史记录，支持按状态筛选、重新下载、打开文件位置
- **主题切换** — 内置浅色/深色/跟随系统三种主题模式
- **中英双语** — 界面语言即时切换，无需重启
- **认证支持** — HuggingFace / ModelScope Token 认证，支持私有和 gated 仓库
- **HF-Mirror 镜像** — 一键启用国内镜像加速 Hugging Face 访问
- **一键打包** — `build.py` 自动检测系统平台，打包为独立 APP

## 界面预览

应用包含四个主要页面：

| 页面                   | 功能                                       |
| ---------------------- | ------------------------------------------ |
| **ModelScope**   | 输入仓库 ID，获取文件列表，选择下载        |
| **Hugging Face** | 同上，可选开启 HF-Mirror 镜像加速          |
| **下载历史**     | 查看历史记录，按完成/失败筛选，重新下载    |
| **设置**         | 主题、语言、镜像开关、Token 认证、关于信息 |

## 安装与运行

### 环境要求

- Python 3.10+
- PySide6 6.7+
- QFluentWidgets 1.11+

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

### 打包为独立 APP

```bash
python build.py                     # 自动检测平台并打包
python build.py --onefile            # 打包为单个 exe 文件
python build.py --platform windows   # 指定目标平台
python build.py --no-clean           # 跳过清理旧构建
```

打包输出位于 `~/builds/` 目录。

## 项目结构

```
model-downloader/
├── main.py                  # 应用入口
├── build.py                 # 一键打包脚本
├── requirements.txt         # 依赖列表
├── ModelDownloader.spec     # PyInstaller 配置
├── todolist.md              # 待办清单
└── src/
    ├── __init__.py          # 包导出
    ├── main_window.py       # 主窗口 + 仓库页 + 设置页
    ├── downloader.py        # 下载引擎（FileInfo / DownloadTask / RepoProvider）
    ├── download_queue.py    # 下载队列组件（表格 + 进度条）
    ├── download_log.py      # 下载日志组件
    ├── download_history.py  # 下载历史记录管理
    ├── file_select_dialog.py# 树形文件选择对话框
    ├── config.py            # 应用配置（主题/语言/Token/镜像）
    ├── i18n.py              # 中英双语翻译管理
    └── icon/                # 图标资源
        ├── icon.ico         # 应用图标
        ├── huggingface.svg  # HuggingFace 导航图标
        ├── modelscope.svg   # ModelScope 导航图标
        └── history.svg      # 下载历史导航图标
```

## Token 认证

访问私有仓库或 gated repo 需要配置 Token：

1. 打开设置页 → 认证卡片
2. 输入 HuggingFace / ModelScope 的 Access Token
3. 点击右侧链接图标可直达对应平台的 Token 获取页面
4. Token 仅存储在本地配置文件中，仅用于 API 认证

## 许可证

MIT License
