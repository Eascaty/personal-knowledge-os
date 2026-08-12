package io.github.eascaty.knowledge.importer;

public record KnowledgeImportResult(
        String sourceId,
        String sha256,
        String originalName,
        String rawPath,
        boolean duplicate) {
}
