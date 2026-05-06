# Changelog

本文档记录 TalkCut Local 所有 notable changes。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [1.0.0] - 2026-05-07

### 🎉 首个正式版本

#### ✨ 新增功能

- **智能语音分析**
  - 集成 FunASR Paraformer-large 模型，中文识别准确率 95%+
  - 支持词级时间戳，为精细剪辑提供依据
  - 多维度问题检测：语气词、静默片段、语速异常、重复词

- **可视化时间轴编辑器**
  - Canvas 波形图显示
  - 多轨道展示（波形、剪辑、问题标签）
  - 拖拽调整剪辑点
  - 字幕滚动区，点击跳转
  - 键盘逐帧微调（左右方向键）

- **灵活的参数配置**
  - 实时调整检测阈值（滑块控件）
  - 语气词库可视化编辑
  - 一键重新分析（无需重新上传视频）

- **高效的渲染输出**
  - 基于 FFmpeg concat demuxer 无损拼接
  - 流媒体传输，快速预览
  - 一键下载成片

#### 🔧 技术实现

- **后端**
  - Flask Web 服务，提供 RESTful API
  - 模块化设计：transcription、audio_features、issue_detector、auto_cutter、renderer
  - 配置热更新，无需重启服务

- **前端**
  - 原生 HTML5 + Canvas + JavaScript，无框架依赖
  - Fetch API 与后端通信
  - 响应式设计，适配不同屏幕

- **分析引擎**
  - FunASR 1.3.1 适配，支持多种返回格式
  - librosa 音频特征提取
  - 智能剪辑点生成算法

#### 📝 文档

- 完整的技术方案与开发文档
- API 接口文档
- 用户使用指南
- 参数配置与调优指南

#### 🐛 修复的问题

- 修复 FunASR 1.3.1 返回格式适配问题（`timestamp`、`sentence_info`、`sentence_timestamp`）
- 修复 `auto_cutter.py` 中 `issue["start"]` 应为 `issue["time"]` 的字段名错误
- 修复"保留此段"无法精确保留中间段的问题
- 优化大视频文件的内存占用

#### 🔒 安全

- 仅绑定 `127.0.0.1`，外部无法访问
- 所有数据处理均在本地完成，无需上传云端

---

## [0.9.0] - 2026-04-20

### 🚧 Beta 测试版本

#### ✨ 新增功能

- 基础语音识别功能
- 简单的剪辑点标记
- 视频预览功能

#### 🐛 已知问题

- FunASR 格式适配不完善
- 时间轴交互体验有待优化
- 缺少参数配置界面

---

## [0.5.0] - 2026-04-01

### 🚧 Alpha 内部测试版本

#### ✨ 新增功能

- 项目框架搭建
- Flask 后端基础路由
- FFmpeg 视频拼接功能验证

---

## 未来计划

### [1.1.0] - 计划中

- [ ] 多视频批量处理
- [ ] 剪辑预设保存/加载
- [ ] 更多导出格式支持
- [ ] 性能优化（GPU 加速）

### [2.0.0] - 展望

- [ ] 打包为桌面应用（PyInstaller + PyQt）
- [ ] 多语言支持（英语、日语等）
- [ ] AI 文案诊断（本地 LLM）
- [ ] 插件系统

---

## 版本说明

- **版本号格式**：主版本.次版本.修订号
  - 主版本：不兼容的 API 修改
  - 次版本：向下兼容的功能性新增
  - 修订号：向下兼容的问题修正

- **版本状态**：
  - ✅ 稳定版本（Stable）
  - 🚧 测试版本（Beta/Alpha）
  - 🔬 开发版本（Dev）

---

**短链接**：[GitHub Releases](https://github.com/JiaJingLi/talkcut-local/releases)
