package io.github.eascaty.knowledge.domain;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record KnowledgeSearchHit(
        String id,
        String title,
        @JsonProperty("highlighted_title") String highlightedTitle,
        String summary,
        String snippet,
        List<String> tags,
        @JsonProperty("node_id") String nodeId,
        List<String> path,
        double rank,
        @JsonProperty("updated_at") String updatedAt) {
}
