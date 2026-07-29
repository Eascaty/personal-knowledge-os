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

- 确认父目录 `/Users/zhaoxl/ai` 存在且为空。
- 按用户最终要求将唯一项目根目录确定为 `/Users/zhaoxl/ai/knowledge`。
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

- 将源码、配置、文档、测试、脚本、launchd 模板和静态站同步到 `/Users/zhaoxl/ai/knowledge`。
- 未复制临时工作区数据库或临时备份；在正式目录重新生成干净 SQLite。
- 在正式目录执行 `scripts/run-pipeline`：0失败、发布门禁通过、健康状态 PASS、网络请求0。
- 在正式目录重新执行18项测试：全部通过。
- 正式目录健康检查：SQLite integrity PASS、外键0异常、隐私0异常、断链0。
- 在 `exports/private/backups/` 生成并验证初始 SQLite 一致性快照。
- 使用本地浏览器完成桌面与手机响应式验收；技术分类导航正常，PWA资源全部返回成功，控制台0错误。
- 在正式项目内初始化本地 Git；基线提交为 `a9b0c5a`，未配置远程仓库、未上传内容。
