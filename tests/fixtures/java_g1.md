# Java G1 垃圾回收器排障笔记

G1 是 JVM 中面向大堆的垃圾回收器。排查 Java 服务停顿时，应同时观察 GC 日志、Region 使用率、Mixed GC 周期和晋升失败，而不是只看平均暂停时间。

本地实践步骤：

1. 保留问题时间段的 GC 日志。
2. 对齐应用延迟与 Young GC、Remark、Cleanup、Mixed GC 时间线。
3. 检查堆占用、对象分配速率和 Humongous Region。
4. 修改参数后使用同一压测样本复验。

这份资料应进入“技术 / 程序员 / Java开发 / JVM / 垃圾回收 / G1”。
