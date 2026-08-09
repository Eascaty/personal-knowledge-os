# 贡献指南

感谢你愿意改进 Personal Knowledge OS。本项目优先保证本地数据安全、流程幂等和公开构建不泄露私人知识。

## 开始之前

1. 先阅读 `AGENTS.md` 与 `docs/knowledge-system-design.md`。
2. 从一个 GitHub Issue 开始，明确问题、边界和验收标准。
3. 不要提交真实笔记、数据库、账号导出、访问令牌或其他个人数据。
4. 对架构、数据结构或安全边界的修改，需要同步更新设计文档和决策记录。

## 本地验证

项目要求 Python 3.9 或更高版本，不依赖付费 API。提交前运行：

```bash
./scripts/test
./scripts/doctor
```

涉及 Java 服务时还需要 Java 21，并运行：

```bash
./scripts/java-test
```

无需预装 Maven；项目内 Wrapper 会下载并校验 Maven 3.9.11。Java 构建必须保持至少80%指令覆盖率和60%分支覆盖率。

涉及完整流水线时再运行：

```bash
./scripts/run-pipeline
```

## 分支和提交

- 分支命名：`feature/<topic>`、`fix/<topic>` 或 `docs/<topic>`。
- 一个提交只解决一个明确问题。
- 推荐使用中文、单一职责提交，例如 `Java：增加只读查询`、`测试：补充隐私边界`、`文档：更新运行说明`。
- Pull Request 必须说明变更原因、影响和验证方式。

## 隐私与样例

- 测试只能使用 `tests/fixtures/` 中的虚构样例。
- `inbox/`、`data/`、生成的 `vault/` 和私密导出不得进入提交。
- 新增发布能力时，必须证明默认仍然离线、私密并且不会自动上传。
