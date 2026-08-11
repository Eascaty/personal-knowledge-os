package io.github.eascaty.knowledge.domain;

import com.fasterxml.jackson.annotation.JsonProperty;

public record RelationEdge(
        String id,
        @JsonProperty("from_node_id") String fromNodeId,
        @JsonProperty("to_node_id") String toNodeId,
        @JsonProperty("relation_type") String relationType,
        String label,
        double confidence) {
}
