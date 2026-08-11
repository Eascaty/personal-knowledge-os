package io.github.eascaty.knowledge.contract;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.eascaty.knowledge.api.ApiResponse;
import io.github.eascaty.knowledge.domain.KnowledgeDocumentSummary;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class CanonicalContractTest {

    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
    private final Path contractRoot = Path.of("..", "..", "packages", "contracts");

    @Test
    void summaryFieldsMatchCanonicalKnowledgeDocument() throws Exception {
        Path examplePath = contractRoot.resolve("examples/canonical-v1.json");
        Path schemaPath = contractRoot.resolve("canonical.schema.json");
        assertThat(examplePath).isRegularFile();
        assertThat(schemaPath).isRegularFile();
        try (var input = Files.newInputStream(examplePath)) {
            JsonNode canonical = objectMapper.readTree(input);
            JsonNode source = canonical.path("documents").get(0);
            KnowledgeDocumentSummary summary = new KnowledgeDocumentSummary(
                    source.path("id").asText(),
                    source.path("title").asText(),
                    source.path("summary").asText(),
                    objectMapper.convertValue(source.path("tags"),
                            objectMapper.getTypeFactory().constructCollectionType(List.class, String.class)),
                    source.path("node_id").asText(),
                    objectMapper.convertValue(source.path("path"),
                            objectMapper.getTypeFactory().constructCollectionType(List.class, String.class)),
                    source.path("updated_at").asText());

            JsonNode api = objectMapper.valueToTree(ApiResponse.of(summary));

            assertThat(api.path("api_version").asText()).isEqualTo("v1");
            for (String field : List.of(
                    "id", "title", "summary", "tags", "node_id", "path", "updated_at")) {
                assertThat(api.path("data").path(field))
                        .as("canonical field %s", field)
                        .isEqualTo(source.path(field));
            }
        }

        JsonNode schema = objectMapper.readTree(schemaPath.toFile());
        JsonNode required = schema.path("$defs").path("document").path("required");
        List<String> requiredFields = new ArrayList<>();
        required.forEach(item -> requiredFields.add(item.asText()));
        for (String field : List.of(
                "id", "title", "summary", "tags", "node_id", "path", "updated_at")) {
            assertThat(requiredFields).contains(field);
        }
    }
}
