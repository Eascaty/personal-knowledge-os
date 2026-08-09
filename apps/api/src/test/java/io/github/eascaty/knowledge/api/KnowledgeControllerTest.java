package io.github.eascaty.knowledge.api;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import io.github.eascaty.knowledge.domain.HealthStatus;
import io.github.eascaty.knowledge.domain.KnowledgeDocument;
import io.github.eascaty.knowledge.domain.KnowledgeDocumentSummary;
import io.github.eascaty.knowledge.domain.PageResult;
import io.github.eascaty.knowledge.repository.KnowledgeQueryRepository;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(KnowledgeController.class)
class KnowledgeControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private KnowledgeQueryRepository repository;

    @Test
    void exposesVersionedHealthContract() throws Exception {
        when(repository.health()).thenReturn(
                new HealthStatus("UP", "personal-knowledge-service", "available", 1));

        mockMvc.perform(get("/api/v1/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.api_version").value("v1"))
                .andExpect(jsonPath("$.data.status").value("UP"))
                .andExpect(jsonPath("$.data.schema_version").value(1));
    }

    @Test
    void searchesWithBoundedPagination() throws Exception {
        KnowledgeDocumentSummary summary = new KnowledgeDocumentSummary(
                "doc-public", "G1 垃圾回收", "摘要", List.of("G1"),
                "java-g1", List.of("技术", "Java开发", "JVM", "G1"),
                "2026-08-09T00:00:00Z");
        when(repository.findDocuments("G1", 0, 20))
                .thenReturn(new PageResult<>(0, 20, 1, List.of(summary)));

        mockMvc.perform(get("/api/v1/search").param("q", "G1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.items[0].node_id").value("java-g1"));
    }

    @Test
    void returnsStableNotFoundError() throws Exception {
        when(repository.findDocument("missing")).thenReturn(Optional.<KnowledgeDocument>empty());

        mockMvc.perform(get("/api/v1/documents/missing"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.api_version").value("v1"))
                .andExpect(jsonPath("$.data.code").value("knowledge_not_found"));
    }
}
