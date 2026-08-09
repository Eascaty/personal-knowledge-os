# 项目状态

- 更新时间：2026-08-10（Asia/Shanghai）
- 阶段：v0.3.1 已发布，GitHub Pages 公开 Demo 实施中
- 总体状态：Python MVP 与 Java J1 均可运行；仓库安全、可复现构建、CI 质量门禁、Release 资产与隔离公开 Demo 已补齐

## 已实现

- 系统采用严格的专业母子树，并允许无限增加一级模块和子级。
- 当前已知主干：
  - `金融 / 财经 / 信用卡 / 美股`
  - `AI / Agent / 智能体`
  - `技术 / 程序员 / Java开发`
- Java 开发允许继续展开 JVM、并发、Spring、数据库、微服务等专业子树。
- 核心处理在 Mac 本地完成，不使用付费模型 API。
- 最终知识库需要在线随时访问，Mac 关机后线上现有版本仍可打开。
- 推荐使用 Cloudflare Pages 静态托管和 Cloudflare Access 私密登录。
- 账号聊天接入与批量网页爬虫暂缓。
- Python 3.9 标准库 CLI 与 SQLite schema。
- 文件扫描、SHA-256 去重、不可变 raw、Markdown 标准化。
- 文本、Markdown、代码、HTML、DOCX；PDF 可选调用本地 `pdftotext`。
- 规则提炼器默认零依赖运行；可选本地 Ollama。
- 三阶段可重试队列、失败隔离、FTS5 中文搜索。
- 严格逐级母子分类、Vault、canonical JSON、搜索和关系图数据。
- 原生 HTML/CSS/JS 静态网站、响应式、PWA、private/public 隔离。
- 项目锁、SQLite 一致性备份、隐私、断链、数据库和发布门禁。
- `scripts/run-pipeline` 单命令离线全链路。
- Java 21 + Spring Boot 3.5 领域模型、SQLite 只读仓储与 API v1。
- 健康检查、分类树、公开知识列表/详情/搜索接口。
- Java API 结构性排除 private 内容、`origin`、`raw_path` 和绝对路径。
- Java HTTP 默认仅监听 `127.0.0.1`，外部监听必须显式设置环境变量。
- launchd 项目内模板，未修改 macOS 系统目录。

## 已验证环境

- 电脑：Apple Silicon M3
- 内存：16GB
- 可用磁盘：约247GB（验证时）
- SQLite：支持 FTS5 与 trigram
- 推荐本地模型规模：4B–8B 量化模型，单并发

## 最近验证

- Python 3.9 语法解析通过。
- 18 项 unittest 全部通过。
- 三份样例生成9个任务，全部完成。
- 重复运行不新增资料或任务。
- 金融、AI、Java/G1 三条路径全部正确。
- 发布门禁会拒绝 private 候选包冒充 public。
- 分类节点删除后资料进入“待归类”，不会生成孤立引用。
- symlink 和越界 raw 路径回归测试通过。
- SQLite、隐私、断链、PWA 缓存和公开过滤检查通过。
- 正式项目目录已完成干净初始化、18项复验与一致性初始备份。
- 桌面端和手机端浏览器验收通过，页面交互正常且控制台0错误。
- 已完成首份真实资料 `2025.10.20.md` 的复制导入演示：原桌面文件未修改，1份资料完成3/3个流水线任务，搜索、网站构建、发布门禁与健康检查均通过。
- GitHub CLI 2.97.0 已从官方 Release 安装并通过 v2rayN 本地代理登录为 `Eascaty`。
- 已选择 `Eascaty/personal-knowledge-os`、Public 与 Apache-2.0，并完成许可证、贡献指南、安全策略、Issue/PR 模板、Dependabot 和 CI 的本地准备。
- 已建立 Java 21 + Spring Boot 增量演进路线；现有 Python MVP 保持可运行，不做无价值重写。
- 已创建私有安全暂存仓库和草稿 PR #1；首次 CI 暴露测试入口依赖 macOS `zsh`，已改为跨平台 POSIX `sh`。
- PR #1 已保留全部分步提交并合并；仓库 `Eascaty/personal-knowledge-os` 已切换为 Public。
- Java J1 使用 Temurin JDK 21.0.12 与 Maven 3.9.11 完成构建；7 项 Java 测试全部通过。
- Java 与 Python 联合复验通过：Java 7/7、Python 18/18，JaCoCo 报告已生成。
- Spring Boot 本机 HTTP 冒烟通过：schema v1 状态 `UP`，分类树正确，private 资料未进入公开列表。
- 最终健康检查 PASS：隐私问题0、密钥匹配0、断链0。
- Java J1 PR #6 已保留全部分步提交并合并，关联 Issue #5 已自动关闭。
- `v0.3.0` Java J1 版本已发布；J2 中文全文搜索已建立为 Issue #10。
- Maven Wrapper 3.9.11 已固定下载地址与 SHA-256，克隆后无需预装 Maven。
- Java 覆盖率为指令88.2%、分支67.5%，CI 门槛分别为80%和60%。
- `main` 已要求 PR 和四项 CI，禁止强推/删除；管理员同样受保护。
- 已启用 CodeQL、Dependabot 安全更新、Secret Scanning、Push Protection 和私密漏洞报告。
- 仓库 topics、CODEOWNERS、跨平台行尾策略和 J2 里程碑已补齐。
- PR #12 已保留4条中文分步提交并合并；`v0.3.1` 已附带正式 JAR 与 SHA-256 发布。
- 最终 main CI 4/4 通过；CodeQL 三语言、Secret Scanning 和 Dependabot 安全告警均为0。
- README 已重构为面向首次使用者的中文项目首页，补齐项目用途、适用人群、三分钟体验、日常流程、数据目录、隐私边界、Java API、FAQ 与路线图。
- README 已加入经过用户确认可公开使用的本地知识地图效果图，并同步 Spring Boot 版本标识至3.5.16。
- 公开 Demo 构建器只读取3份固定虚构资料，在临时目录生成独立 SQLite 和 public 站点，不访问本机真实知识库。
- Python 测试增加为19项；新增 Public Demo CI 和 GitHub Pages 自动部署工作流。

## 尚需用户以后完成

1. Java J2：将基础搜索升级为 FTS5/Lucene 中文全文搜索并记录基准。
2. 对大体量、跨子主题的综合笔记增加按标题分块和多知识卡片生成。
3. 如需持续后台运行，再明确选择是否安装 launchd 模板。
4. 如需线上访问真实私密知识，再登录 Cloudflare 并配置 Access 精确邮箱策略。
