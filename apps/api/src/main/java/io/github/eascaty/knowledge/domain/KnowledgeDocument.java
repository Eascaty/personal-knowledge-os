package io.github.eascaty.knowledge.domain;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record KnowledgeDocument(
        String id,
        String title,
        String body,
        String summary,
        List<String> tags,
        @JsonProperty("node_id") String nodeId,
        List<String> path,
        @JsonProperty("updated_at") String updatedAt,
        KnowledgeSource source,
        List<RelationEdge> relations) {
}
