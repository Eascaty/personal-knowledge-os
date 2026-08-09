# Exports

公开导出结构：

```text
exports/
└── public/      # 用户知识唯一允许对外同步的目录
```

私密健康报告和备份已经集中到 `workspace/exports/private/`。任何自动发布流程必须以白名单方式构建 `public/`，不能直接复制整个知识库或 workspace。
