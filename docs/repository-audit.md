# GitHub 发布后缺口审计

- 日期：2026-08-09（Asia/Shanghai）
- 仓库：`Eascaty/personal-knowledge-os`
- 审计范围：开源元数据、分支策略、安全功能、依赖维护、构建复现、CI、Release 与简历展示
- 结果：高优先级缺口已在 PR #12 补齐，并随 `v0.3.1` 发布。

## 已补齐

- `main` 必须通过 Pull Request，Java 21 与 Python 3.9/3.12/3.13 为必需检查。
- 管理员同样受保护，禁止强推和删除主分支；仅允许普通合并以保留分步提交。
- Secret Scanning、Push Protection、Dependabot 安全更新、私密漏洞报告与 CodeQL 已启用。
- Maven Wrapper 固定 Maven 3.9.11，并校验分发 SHA-256。
- `.gitattributes` 固定 shell 为 LF、Windows cmd 为 CRLF，避免跨平台入口损坏。
- Java CI 增加10分钟超时、重复运行取消、80%指令与60%分支覆盖率门槛。
- Dependabot 不再自动把 Spring Boot 3 升级到4；跨大版本迁移必须单独设计和验证。
- Python 与 Java 版本统一为 `0.3.1`，正式 JAR 不再带 `SNAPSHOT`。
- CODEOWNERS、仓库 topics、J2 里程碑和安全 Issue 导航已补齐。

## 已验证

- Java：7/7 测试通过。
- Python：18/18 测试通过。
- JaCoCo：指令88.2%、分支67.5%。
- doctor：数据库、隐私、密钥和断链检查 PASS。
- Git 公开归档不包含真实知识、SQLite、私密导出或生成站点。
- GitHub Dependabot 安全告警：0。
- v0.3.1 Release 已包含正式 Java JAR 与 SHA-256 校验文件。

## 有意留到后续

- J2：FTS5/Lucene 中文全文搜索、安全高亮和性能基准。
- J3：Java 幂等导入与事务迁移。
- J4：OpenAPI、Docker 与可部署服务。
- 使用虚构公开资料制作 GitHub Pages/Cloudflare Pages 演示，不公开真实知识。
- 大型综合笔记按标题拆成多知识卡片。

这些项目属于新功能或架构里程碑，不应混入 v0.3.1 工程加固补丁。
