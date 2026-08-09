package io.github.eascaty.knowledge.domain;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record KnowledgeDocumentSummary(
        String id,
        String title,
        String summary,
        List<String> tags,
        @JsonProperty("node_id") String nodeId,
        List<String> path,
        @JsonProperty("updated_at") String updatedAt) {
}
