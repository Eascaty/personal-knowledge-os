package io.github.eascaty.knowledge.contract;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.eascaty.knowledge.api.ApiResponse;
import io.github.eascaty.knowledge.domain.KnowledgeDocumentSummary;
import java.io.InputStream;
import java.util.List;
import org.junit.jupiter.api.Test;

class CanonicalContractTest {

    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

    @Test
    void summaryFieldsMatchCanonicalKnowledgeDocument() throws Exception {
        try (InputStream input = getClass().getResourceAsStream("/canonical-contract.json")) {
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
    }
}
