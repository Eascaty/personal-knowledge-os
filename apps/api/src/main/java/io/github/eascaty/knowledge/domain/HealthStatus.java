package io.github.eascaty.knowledge.domain;

import com.fasterxml.jackson.annotation.JsonProperty;

public record HealthStatus(
        String status,
        String service,
        String database,
        @JsonProperty("schema_version") Integer schemaVersion) {
}
