# launchd 自动调度模板

模板每15分钟调用一次项目内 `scripts/run-pipeline`，自动扫描 `inbox/`、
处理本地数据库、重建网站并生成健康报告。默认不联网，也不会自动发布。

本工程不会自行写入 `~/Library/LaunchAgents`，所以没有修改任何项目外系统
设置。以后需要常驻调度时，再把 `__PROJECT_ROOT__` 替换为
`/Users/zhaoxl/ai/knowledge`，并由用户明确选择是否安装到 launchd。
