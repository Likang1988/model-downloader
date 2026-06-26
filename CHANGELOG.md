# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- 支持 Hugging Face 和 ModelScope 双平台模型与数据集下载
- 树形文件选择对话框，支持多选/全选
- 下载队列管理，支持暂停/恢复/取消，最多 3 个并发
- 下载历史记录，持久化存储，支持按状态筛选、重新下载、打开文件位置
- 主题切换（浅色/深色/跟随系统）
- 中英双语界面语言切换
- HuggingFace / ModelScope Token 认证，支持私有和 gated 仓库
- HF-Mirror 镜像加速支持
- 一键打包脚本 `build.py`，自动检测系统平台

### Fixed

- 修复重启后暂停任务不显示在列表中的问题
- 修复删除任务后重新添加不显示的问题
- 修复 ModelScope 数据集下载 URL 缺少 `/datasets/` 前缀的问题
- 修复保存路径重启后不恢复的问题
