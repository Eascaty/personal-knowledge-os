# 操作记录

> 本文件记录对项目产生实质影响的操作，不记录密码、Cookie、Token 或完整私密内容。

## 2026-07-27

### 需求与架构梳理

- 确认系统底线：无付费 API、本地优先、可自动运行。
- 确认最终需要在线随时访问，而不是仅有本地文件。
- 确认专业信息架构是严格的母子级链路。
- 确认当前一级模块至少包括金融、AI、技术，但不限制未来增加其他模块。
- 确认 Java 开发需要继续展开 JVM、并发、Spring、数据库、微服务等子级。
- 确认账号接入与网页爬虫暂不进入第一阶段。

### 本机只读检查

- 检查 Mac 硬件：Apple Silicon M3、16GB 内存。
- 检查可用磁盘：约247GB。
- 检查基础命令与工具可用性。
- 验证本机 SQLite 支持 FTS5 trigram 中文检索。
- 未安装知识库运行依赖，未下载本地模型。

### 方案研究

- 调研本地 LLM Wiki、不可变原始资料、Markdown 编译知识库和 lint 工作流。
- 调研 Ollama、SQLite FTS5、Trafilatura、MarkItDown、OCRmyPDF、whisper.cpp。
- 调研 Cloudflare Pages 免费限制、静态访问、Access 保护和 GitHub Pages 限制。
- 为 Codex 添加了 `openaiDeveloperDocs` 官方文档 MCP 配置；后续会话可能需要重启后加载。

### 交互示意

- 创建第一版通用知识网络示意。
- 根据用户反馈，改为专业母子树。
- 融合金融、AI、技术三条主干和 Java 开发子树。

### 文档初始化

- 确认父目录 `$HOME/ai` 存在且为空。
- 按用户最终要求将唯一项目根目录确定为 `$HOME/ai/knowledge`。
- 创建总体设计活文档、工作流、分类配置、状态、决策和操作记录。
- 在项目外的系统依赖保持不变；实现阶段先使用项目内代码和现有 Python/SQLite。

## 2026-07-30

### 全链路实现

- 完成 Python 3.9 标准库项目、SQLite schema、FTS5、任务队列和 CLI。
- 完成文件接收、SHA-256 去重、不可变 raw、Markdown、逐级分类和 Vault。
- 完成原生静态网站、中文搜索、专业树、证据区、知识图、响应式和 PWA。
- 完成数据库、磁盘、隐私、断链、构建清单、备份与发布门禁。
- 增加 `scripts/run-pipeline` 单命令离线闭环和 launchd 项目内模板。
- 未安装任何系统依赖，未修改项目外的持久用户目录，未执行网络发布。

### Code review 修复

- 修复 private 候选包可能通过 public 发布门禁的问题。
- 修复分类节点退休后产生孤立文档引用的问题。
- 拒绝 symlink 输入并约束 raw 读取只能位于 `data/raw/`。
- 核心、网站、doctor、gate、backup 与完整自动化使用统一项目锁。
- 公开来源 URL 删除全部查询参数和 fragment。
- 静态资源改为短缓存验证；网站回滚目录使用随机唯一名称。
- 未知 SQLite schema 版本不再被静默覆盖。

### 验证

- Python 3.9 语法解析通过。
- 18 项 unittest 全部通过。
- zsh 脚本语法、launchd plist 与前端 JavaScript 语法通过。
- 三份样例完成9个任务；金融、AI、Java/G1 路径全部正确。
- 第二次运行0新增、3重复、0新任务。
- 本地健康检查与发布门禁通过；所有检查网络请求为0。

### 正式目录交付

- 将源码、配置、文档、测试、脚本、launchd 模板和静态站同步到 `$HOME/ai/knowledge`。
- 未复制临时工作区数据库或临时备份；在正式目录重新生成干净 SQLite。
- 在正式目录执行 `scripts/run-pipeline`：0失败、发布门禁通过、健康状态 PASS、网络请求0。
- 在正式目录重新执行18项测试：全部通过。
- 正式目录健康检查：SQLite integrity PASS、外键0异常、隐私0异常、断链0。
- 在 `exports/private/backups/` 生成并验证初始 SQLite 一致性快照。
- 使用本地浏览器完成桌面与手机响应式验收；技术分类导航正常，PWA资源全部返回成功，控制台0错误。
- 在正式项目内初始化本地 Git；基线提交为 `a9b0c5a`，未配置远程仓库、未上传内容。

### 首份真实资料演示（2026-07-30 00:54:24 +0800）

- 确认桌面最新项目是 macOS Alias `2025.10.20.md的替身`，实际内容文件为 `$HOME/Desktop/2025.10.20.md`。
- 只读检查确认其为 Java 综合学习笔记；将副本放入 `inbox/files/`，未移动或修改桌面原文件。
- 执行 `scripts/run-pipeline`：导入1份、完成3/3个任务、0重试、0失败、网络请求0。
- 生成1份知识文档；网站构建、private 发布门禁与本地健康检查全部通过。
- 搜索“泛型”和“hashCode”均可命中。规则分类当前落在 `技术 / 程序员 / Java开发 / JVM / 垃圾回收 / G1`。
- 识别到综合长文档的分类粒度问题：后续应按 Markdown 标题切分为多张知识卡片，再分别挂入 Java基础、JVM、并发等节点；本次不改写用户原文。

### GitHub 开源准备（2026-08-09 18:06:27 +0800）

- 用户确认公开仓库目标为 `Eascaty/personal-knowledge-os`，许可证为 Apache-2.0，并保留 Python MVP、增加 Java 模块。
- 审计本地 Git：无远程仓库；真实知识、SQLite 数据库、私密导出和生成站点均未被跟踪。
- 运行现有测试套件，18/18 通过。
- 从 GitHub CLI 官方 Release 下载并按官方 SHA-256 校验 `gh 2.97.0`；通过本机 v2rayN SOCKS 代理完成 `Eascaty` 登录。
- 增加许可证、贡献指南、安全策略、Issue/PR 模板、Dependabot、GitHub Actions CI 与 Java 增量演进路线。
- 本阶段尚未创建远程仓库或上传代码，等待最终本地验证。

### GitHub Actions 首次 CI 修复（2026-08-09）

- 已创建私有安全暂存仓库 `Eascaty/personal-knowledge-os`，并推送开源候选分支、创建草稿 PR #1。
- 首次 GitHub Actions 在 Python 3.9、3.12、3.13 三个任务中均于测试入口退出，错误为 `./scripts/test: cannot execute: required file not found`。
- 根因是测试脚本使用 macOS 自带、Ubuntu Runner 默认不存在的 `/bin/zsh`，并写死系统 Python 路径。
- 经用户确认，将测试入口改为 POSIX `sh`，使用可移植的项目路径解析和 Actions 已配置的 `python3`。

### GitHub 开源首发完成（2026-08-09）

- CI 修复提交 `2ffc6de` 已推送，GitHub Actions 的 Python 3.9、3.12、3.13 三个任务全部通过。
- PR #1 已使用普通合并进入 `main`，保留许可证、文档、协作配置、CI 修复等全部中文分步提交。
- 仓库 `Eascaty/personal-knowledge-os` 已由私有安全暂存切换为 Public。
- 公开前后检查确认真实知识、SQLite 数据库、私密导出和生成站点均未进入 Git 跟踪范围。

### Java J1 领域模型与只读 API（2026-08-09 19:23 +0800）

- 从 GitHub Issue #5 建立 `agent/java-j1-readonly-api` 功能分支，采用 Java 21、Spring Boot 3.5.3、Maven 和 SQLite JDBC。
- 增加知识条目、分类节点、脱敏来源和关系边领域模型，以及带 `api_version=v1` 的健康、分类树、列表、详情和搜索接口。
- SQLite 适配器采用只读连接；知识查询强制过滤 `public`，API 来源结构不包含 `origin`、`raw_path` 或绝对路径。
- 使用官方 SHA-256/SHA-512 校验临时 Temurin JDK 21.0.12 与 Maven 3.9.11，未替换本机 Java 8 或修改系统级配置。
- Java 7 项测试全部通过，覆盖 canonical JSON 契约、MockMvc、SQLite 集成、private 过滤、路径脱敏和 SQL 通配符转义。
- Maven `verify`、JaCoCo 报告和原有 Python 18 项测试全部通过；GitHub Actions 已增加独立 Java 21 任务。
- 使用打包后的 Spring Boot JAR 在 `127.0.0.1:18080` 完成真实 SQLite HTTP 冒烟：健康 `UP`、schema v1、分类根节点正确；因真实资料均为 private，公开列表为0。
- 冒烟后正常关闭临时服务；最终 doctor 为 PASS，隐私问题0、密钥匹配0、断链0。
- 代码审查后将 Spring Boot 默认监听地址固定为 `127.0.0.1`，并为 Maven 增加每月 Dependabot 检查。
