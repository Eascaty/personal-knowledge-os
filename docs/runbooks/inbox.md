# Inbox

`workspace/inbox/` 是本机唯一的用户投放入口，除本运行手册外不进入 Git。

计划结构：

```text
workspace/inbox/
├── files/       # PDF、Word、Markdown、文本等
└── urls.txt     # 一行一个手工网址
```

日常使用时把文件放进 `workspace/inbox/files/`，再运行 `./scripts/run-pipeline`。流水线复制原始资料并按内容哈希去重，不覆盖投放文件。
