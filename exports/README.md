# Exports

计划结构：

```text
exports/
├── private/     # 私密导出或备份，不公开
└── public/      # 唯一允许对外同步的目录
```

任何自动发布流程必须以白名单方式构建 `public/`，不能直接复制整个知识库。

