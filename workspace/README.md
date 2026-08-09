# Private workspace

`workspace/` 是本机私密运行区，除本说明外整体不进入 Git。

```text
workspace/
├── inbox/files/       # 用户投入入口
├── data/raw/          # 不可变原始副本
├── data/normalized/   # 标准化文本
├── data/state/        # SQLite 与项目锁
├── data/quarantine/   # 失败隔离
├── vault/             # 可阅读知识树
└── site/              # 私密站点数据与构建结果
```

原始资料只追加、不覆盖；公开发布仍只能使用根目录 `exports/public/` 或隔离的虚构 Demo 构建。
