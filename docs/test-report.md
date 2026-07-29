# 测试报告

- 日期：2026-07-30（Asia/Shanghai）
- 运行环境：macOS、Python 3.9.6、SQLite FTS5 trigram
- 结果：18 项测试全部通过
- 正式目录复验：`/Users/zhaoxl/ai/knowledge`
- 最终健康检查：PASS；隐私问题0；断链0；网络请求0
- 浏览器验收：桌面1280×720与手机390×844布局正常，分类导航可交互，控制台0错误

## 自动测试范围

- raw 不可变与 SHA-256 幂等去重
- Java/G1 深层母子分类
- 未知资料进入“待归类”
- 非法跨级模型路径被拒绝
- 失败重试和最终隔离
- 分类节点退休后的自动迁移
- symlink 输入与 raw 路径越界
- 收件箱到网站的完整自动化
- 再次运行不重复建库
- 项目锁竞争
- SQLite WAL 一致性快照
- 凭据扫描且报告不泄露凭据值
- 断链检查零网络请求
- private 候选包不能冒充 public 发布
- public 构建剔除 private 内容和 URL 查询参数
- private noindex、JSON no-store 和 PWA 不缓存知识数据
- 坏 canonical 不替换上一正常站点

## 端到端结果

```text
3 个输入
→ 3 个 source
→ 9 个 extract/enrich/index 作业
→ 9 个成功，0 个失败
→ 3 篇知识文档
→ 25 个分类节点
→ 静态网站与发布门禁 PASS
```

分类结果：

```text
AI Agent 的长期记忆
→ AI / Agent / 智能体

信用卡权益与美股消费场景
→ 金融 / 财经 / 信用卡 / 美股

Java G1 垃圾回收器排障笔记
→ 技术 / 程序员 / Java开发 / JVM / 垃圾回收 / G1
```

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python3 -B -m unittest discover -s tests -v

zsh -n scripts/*
plutil -lint ops/launchd/com.local.knowledge-os.plist.template
node --check src/knowledge_os/site/assets/app.js
```
