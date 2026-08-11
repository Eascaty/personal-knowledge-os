# Shared contracts

这里保存跨 Python、Java、Web 和未来 App 的版本化契约：

- `canonical.schema.json`：静态知识数据格式。
- `openapi.yaml`：HTTP API v1 格式。
- `examples/canonical-v1.json`：Python 与 Java 共用的固定虚构契约样例。

契约只描述结构，不包含真实用户知识或凭据。破坏性变更必须新增版本；v1 文件只能向后兼容地增加可选字段。
