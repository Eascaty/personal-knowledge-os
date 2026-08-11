package io.github.eascaty.knowledge.domain;

import com.fasterxml.jackson.annotation.JsonProperty;

public record KnowledgeSource(
        String kind,
        @JsonProperty("original_name") String originalName,
        String sha256) {
}
