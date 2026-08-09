# 个人知识体系总体设计

> 状态：活文档  
> 版本：0.4.0-dev
> 更新时间：2026-08-10（Asia/Shanghai）
> 项目根目录：`$HOME/AI/knowledge`

## 1. 目标

建设一套本地优先、零付费 API、可自动运行并能在线随时访问的个人知识系统。

用户最终体验：

```text
投入本地文件
→ 系统自动解析与去重
→ 本地 AI 提炼知识
→ 逐级归入专业母子树
→ 更新搜索、关系图与报告
→ 自动构建私密网站
→ 在手机或任意电脑登录访问
```

网站已经发布的版本由云端静态托管，因此 Mac 关机后仍然可以打开；Mac 只负责处理新资料和发布新版本。

实现状态：本地入库、分类、搜索、知识图、静态站、检查和发布适配代码已完成；Java 21 只读领域 API 的 J1 里程碑也已完成。
虚构公开资料已经通过 GitHub Pages 提供在线 Demo；真实私密知识的线上地址仍需用户以后登录 Cloudflare 并启用 Access。本地默认零网络请求。

## 2. 当前范围

### 第一阶段包含

- 本地文件投入
- Markdown、文本、代码、HTML、DOCX 等本地资料
- 文本型 PDF（本机存在免费 `pdftotext` 时）
- 原始资料保存
- 内容哈希与重复检测
- 本地模型摘要、分类和知识提炼
- 专业母子树
- Markdown 知识页
- 中文全文搜索
- 可点击知识地图
- 私密/公开静态网站
- 自动构建、检查与安全回滚

### 暂缓

- ChatGPT/Gemini 账号历史接入
- 手工网址下载与网页抓取
- 扫描 PDF OCR
- 浏览器实时聊天采集
- 批量网页爬虫
- RSS 全网订阅
- 大规模向量数据库
- 公开原始附件

暂缓项目以后通过新的输入适配器接入，不改变核心数据结构。

## 3. 信息架构

系统包含两种关系，必须分开。

### 3.1 专业母子树

这是稳定分类骨架：

```text
我的知识体系
├── 金融
│   └── 财经
│       └── 信用卡
│           └── 美股
├── AI
│   └── Agent
│       └── 智能体
├── 技术
│   └── 程序员
│       └── Java开发
│           ├── Java基础
│           ├── JVM
│           │   ├── 内存模型
│           │   ├── 类加载
│           │   ├── 垃圾回收
│           │   │   ├── G1
│           │   │   └── ZGC
│           │   └── 性能诊断
│           ├── 并发编程
│           ├── Spring生态
│           ├── 数据库
│           ├── 微服务
│           └── 工程实践
└── 未来新增一级模块
```

规则：

- 一级模块数量不设上限。
- 树深度不设固定上限。
- 一份资料只有一个主路径。
- 一级至三级默认由用户定义并锁定。
- AI 只在允许层级以下增加子节点。
- 用户定义的专业链路优先于通用语义判断。

### 3.2 辅助知识关系

辅助关系不改变专业目录，包括：

- `supports`
- `contradicts`
- `extends`
- `derived_from`
- `mentions`
- `used_in_project`
- `supersedes`
- `related_to`

每条事实性关系必须指向证据段落、页码或来源片段。

## 4. 核心工作流

```text
INBOX
  ↓
RECEIVED
  ↓
EXTRACTED
  ↓
DEDUPED
  ↓
CLASSIFIED
  ↓
ENRICHED
  ↓
INDEXED
  ↓
BUILT
  ↓
PUBLISHED

任何阶段失败 → RETRY → QUARANTINE
```

### 4.1 接收

第一阶段只支持明确输入：

- `workspace/inbox/files/` 中的本地文件
- `workspace/inbox/urls.txt` 中的手工网址

不执行无限递归爬取。

### 4.2 原始保存

- 原始资料只追加、不覆盖。
- 保存来源、时间、MIME 类型和 SHA-256。
- 网页发生变化时保存新版本，不覆盖旧内容。

### 4.3 解析

候选组件：

- HTML：Trafilatura
- Office：MarkItDown
- 普通 PDF：pdfplumber
- 扫描 PDF：OCRmyPDF + Tesseract
- 音视频（后续）：ffmpeg + whisper.cpp

解析后统一生成标准 Markdown 和 JSON 元数据。

### 4.4 去重

在调用本地模型前完成：

1. 原文件 SHA-256
2. 规范化正文 SHA-256
3. 规范 URL
4. 必要时再做近似重复

重复项建立别名，不直接删除。

### 4.5 逐级分类

模型不能一次自由生成完整路径，而是从根节点逐级选择：

```text
选择一级模块
→ 仅查看该父节点的现有子节点
→ 选择已有子节点或提出新子节点
→ 重复，直到最具体的适合位置
```

分类综合以下信号：

- 专业关键词
- SQLite FTS5 搜索结果
- 本地模型结构化判断
- 相邻资料一致性
- 同名、别名和重复检测

不确定资料进入“待归类”，仍可搜索，不阻塞队列。

### 4.6 知识生成

每份资料至少生成：

- 来源笔记
- 摘要
- 关键观点
- 概念和实体
- 开放问题
- 证据引用
- 主路径
- 辅助关系
- AI 状态与版本

AI 输出默认不是事实。状态包括：

- `personal`
- `unverified`
- `supported`
- `contradicted`
- `deprecated`
- `verified-by-practice`

### 4.7 检查

发布前检查：

- 断链
- 孤立节点
- 重复节点
- 缺失来源
- 无证据关系
- 隐私字段
- 路径冲突
- 过大的网页数据包
- 搜索索引可用性

检查失败时不发布。

## 5. 本地技术架构

### 5.1 核心组件

| 模块 | 默认工具 |
|---|---|
| 运行环境 | macOS 自带 Python 3.9+；仅使用标准库即可运行 |
| 只读领域 API | Java 21、Spring Boot 3.5、Maven |
| 状态与知识关系 | SQLite |
| 中文全文检索 | SQLite FTS5 trigram |
| 本地模型 | 可选 Ollama + Qwen3 8B；不可用时规则引擎自动降级 |
| 文档本体 | Markdown + JSON |
| 前端 | 原生 HTML、CSS、JavaScript |
| 浏览器搜索 | 本地静态 JSON + 原生 JavaScript |
| 知识关系图 | 原生 SVG/Canvas 数据视图 |
| 调度 | macOS launchd |
| 版本 | Git |
| 文档导出 | Markdown、JSON、GraphML |
| 虚构公开 Demo | GitHub Pages + GitHub Actions |
| 真实私密知识托管 | Cloudflare Pages + Cloudflare Access |

第一版不要求安装任何依赖，也不采用 Docker、n8n、LangChain、Chroma 或 Neo4j。这样即使没有 Ollama、Node 或 Pandoc，仍可完成确定性的全链路；本地模型只是可选增强。

### 5.2 Java 只读服务边界

`apps/api/` 是现有 Python 流水线的增量消费者，不参与写入：

```text
Python 入库/分类/构建 → SQLite schema v1 ← Java 21 只读 API
                                ↓
                         仅查询 public 内容
```

- Java 服务使用 SQLite 只读连接，不迁移、不建表、不修改任务状态。
- `/api/v1` 响应显式携带 API 版本。
- 知识列表、详情和搜索统一增加 `visibility='public'` 数据库过滤。
- 来源响应只包含类型、文件名和 SHA-256，不返回 `origin`、`raw_path` 或绝对路径。
- 分类树可以读取全部有效分类节点，但不携带用户资料内容。
- J1 采用参数化 `LIKE` 搜索建立 API 契约；J2 再接入 FTS5/Lucene 并记录性能基准。

### 5.3 SQLite 主要表

- `taxonomy_nodes`
- `taxonomy_aliases`
- `sources`
- `source_versions`
- `documents`
- `chunks`
- `placements`
- `entities`
- `relations`
- `jobs`
- `runs`
- `artifacts`
- `deployments`

## 6. 项目目录

项目已经迁移为模块化单仓库：

```text
knowledge/
├── apps/
│   ├── pipeline/       # Python 唯一写入方
│   ├── api/            # Java 21 只读 API
│   └── web/            # 静态网站与 PWA 源码
├── packages/contracts/ # canonical JSON Schema 与 OpenAPI
├── config/             # taxonomy、运行配置模板和本机配置
├── workspace/          # 私密输入、原始资料、SQLite、Vault、私密构建
├── exports/public/     # 用户知识唯一公开候选
├── docs/
├── ops/
├── scripts/
└── tests/e2e/
```

约束：

- 旧脚本入口保持可用，SQLite schema v1、知识 ID、分类 ID 和原始资料哈希不变。
- `workspace/` 除说明文件外整体忽略；原始资料只追加。
- `apps/web/src/` 是手写网站源码唯一位置，`workspace/site/` 只是派生产物。
- Python 顶层旧导入由兼容 facade 保留；实现模块以600行为审查上限。
- 详细边界以 `docs/project-structure.md` 为准。
## 7. 在线访问设计

### 7.1 虚构公开 Demo

GitHub Actions 只检出公开仓库，在隔离临时目录导入 `tests/fixtures/` 中3份固定虚构资料，生成独立 SQLite 和 public 静态站点。只有数据库、构建清单、可见性、隐私、密钥和断链门禁全部通过时，产物才会部署到 GitHub Pages。

公开地址：<https://eascaty.github.io/personal-knowledge-os/>

该工作流不读取维护者电脑，也不能访问真实 `workspace/inbox/`、`workspace/data/state/`、`workspace/vault/` 或 `workspace/site/dist/`。

### 7.2 真实私密知识默认方案

采用 Cloudflare Pages 托管纯静态网站，Cloudflare Access 保护访问。

优点：

- 网站发布后不依赖 Mac 在线。
- 无在线数据库和模型费用。
- 静态访问快。
- 可以回滚历史部署。
- 可使用免费 `*.pages.dev` 地址。

### 7.3 网站数据

线上只上传生成后的站点：

```text
exports/public/
├── index.html
├── assets/
├── data/
│   ├── taxonomy.json
│   ├── modules/
│   ├── search-index/
│   └── graph/
└── reports/
```

不上传：

- 原始 PDF、Word 和账号导出
- SQLite 数据库
- 日志、缓存和隔离文件
- 密钥和部署 Token

### 7.3 私密版与公开版

- 私密版：完整的整理后知识，受 Access 登录保护。
- 公开版：仅包含 `visibility: public` 内容。
- 默认可见性始终为 `private`。

### 7.4 构建与发布限制

```yaml
publish:
  debounce_minutes: 15
  maximum_deployments_per_day: 10
  deploy_only_when_changed: true
  require_lint_success: true
  rollback_on_healthcheck_failure: true
```

发布步骤：

1. 合并连续变更。
2. 生成临时站点。
3. 本地运行结构、搜索和隐私测试。
4. 成功后发布。
5. 检查线上地址。
6. 失败则保留或恢复上一正常版本。

### 7.5 网站形态

- 一级专业模块入口
- 左侧母子目录
- 中间知识正文
- 右侧来源证据和关联知识
- 全文搜索
- 可点击知识图
- 最近新增与周报
- 手机响应式
- PWA 安装与可选离线缓存
- 最后更新时间和部署版本

## 8. 电脑资源影响

已验证电脑为 M3、16GB 内存，适合单并发运行 Qwen3 4B–8B。

预计首次占用：

| 内容 | 估计空间 |
|---|---:|
| Qwen3 8B | 约5.2GB |
| Whisper（后续） | 约0.5GB |
| Python、Node 与解析工具 | 约1–2GB |
| OCR、构建和缓存 | 约1–3GB |
| 合计 | 约8–12GB |

默认保护：

```yaml
minimum_free_disk_gb: 40
maximum_cache_gb: 5
maximum_log_mb: 200
llm_concurrency: 1
run_heavy_jobs_on_battery: false
allow_system_sleep: true
raw_auto_delete: false
```

无任务时工作进程退出。Mac 睡眠时暂停新资料处理，但线上现有版本继续可用。

## 9. 安全与隐私

- 所有输入默认私有。
- 部署凭据存入 macOS Keychain。
- 站点中不包含密码、Cookie、验证码或 API Token。
- 公开构建采用白名单，不采用排除式发布。
- Cloudflare Access 仅允许精确指定的邮箱。
- 增加 `X-Robots-Tag: noindex` 等安全响应头。
- 原始资料不因云端发布而移动或删除。

以后接入聊天记录时，默认不采集临时聊天，并检测凭据、验证码、完整卡号和其他敏感字段。

## 10. 自动化与可恢复性

提供一个默认不安装的 `launchd` LaunchAgent 模板；用户以后选择启用时，定期执行：

```text
./scripts/run-pipeline
```

要求：

- 文件锁防止任务重叠。
- 每阶段独立事务。
- 指数退避与最大重试次数。
- 单条失败不影响其他任务。
- 每日生成健康报告。
- 数据库创建一致性快照。
- 依赖与模型不自动升级。

## 11. 实施阶段

### 阶段 A：本地骨架（已完成）

- Python CLI
- SQLite schema
- taxonomy 导入
- 文件收件箱
- SHA-256 去重
- 标准 Markdown

### 阶段 B：本地智能整理（规则引擎已完成，Ollama 可选）

- Ollama
- 结构化摘要
- 逐级分类
- 证据关系
- FTS5 搜索

### 阶段 C：网站（已完成）

- 专业树界面
- 全文搜索
- 知识地图
- 报告
- 手机适配
- PWA

### 阶段 D：线上发布（虚构公开 Demo 已完成；真实私密站点待账号配置）

- GitHub Pages 虚构公开 Demo
- GitHub Actions 隔离构建与门禁
- Cloudflare Pages
- Cloudflare Access
- 自动构建
- 健康检查
- 回滚

### 阶段 E：扩展输入（暂缓）

- OCR
- 音视频
- ChatGPT/Gemini
- 浏览器采集
- RSS 与合规网页采集

## 12. 第一版验收标准

1. 投入同一文件两次只生成一份资料。
2. 示例 Java 文档进入正确母子路径。
3. 新增允许层级以下的子节点不会破坏锁定主干。
4. 网站可以浏览金融、AI、技术三条主干。
5. 搜索结果能回到来源和证据。
6. 断链或隐私测试失败时禁止发布。
7. Mac 关机后线上已发布版本仍可访问。
8. 未标记 `public` 的内容不进入公开构建。
9. 任务中断后可以继续。
10. 每次实质操作都更新状态和日志。

## 13. 已知边界

- “免费无限”指没有按次 API 费用，不代表没有硬件、磁盘或免费托管额度。
- 在线访问意味着整理后的站点内容存储在托管平台；原始资料仍只在本地。
- 本地模型分类并非绝对正确，不确定内容必须可追踪和纠正。
- Mac 睡眠时不会处理新资料，但不影响线上旧版本。

## 14. 更新规则

本文件是活文档。任何架构、数据边界、技术选型、分类规则或发布策略变更，必须在同一次工作中更新本文件；只有形成长期取舍时才追加决策，只有部署、迁移、恢复或外部状态变化时才追加操作记录。

## 15. 参考资料

- Cloudflare Pages limits: <https://developers.cloudflare.com/pages/platform/limits/>
- Cloudflare Pages pricing: <https://developers.cloudflare.com/pages/functions/pricing/>
- Cloudflare Access policies: <https://developers.cloudflare.com/cloudflare-one/access-controls/policies/>
- Cloudflare Access for `pages.dev`: <https://developers.cloudflare.com/pages/platform/known-issues/#enable-access-on-your-pagesdev-domain>
- GitHub Pages custom workflows: <https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages>
- SQLite FTS5: <https://www.sqlite.org/fts5.html>
- Ollama API: <https://docs.ollama.com/api/introduction>
- macOS launchd: <https://support.apple.com/guide/terminal/script-management-with-launchd-apdc6c1077b/mac>
