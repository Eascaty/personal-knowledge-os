package io.github.eascaty.knowledge.api;

public class KnowledgeNotFoundException extends RuntimeException {

    public KnowledgeNotFoundException(String id) {
        super("未找到公开知识条目：" + id);
    }
}
