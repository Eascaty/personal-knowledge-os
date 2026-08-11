package io.github.eascaty.knowledge.api;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import io.github.eascaty.knowledge.domain.HealthStatus;
import io.github.eascaty.knowledge.domain.KnowledgeSearchHit;
import io.github.eascaty.knowledge.domain.PageResult;
import io.github.eascaty.knowledge.service.KnowledgeQueryService;
import java.util.List;
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
    private KnowledgeQueryService service;

    @Test
    void exposesVersionedHealthContract() throws Exception {
        when(service.health()).thenReturn(
                new HealthStatus("UP", "personal-knowledge-service", "available", 1));

        mockMvc.perform(get("/api/v1/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.api_version").value("v1"))
                .andExpect(jsonPath("$.data.status").value("UP"))
                .andExpect(jsonPath("$.data.schema_version").value(1));
    }

    @Test
    void searchesWithBoundedPagination() throws Exception {
        KnowledgeSearchHit hit = new KnowledgeSearchHit(
                "doc-public", "G1 垃圾回收", "[[G1]] 垃圾回收", "摘要", "[[G1]] 使用 Region",
                List.of("G1"),
                "java-g1", List.of("技术", "Java开发", "JVM", "G1"),
                -2.5,
                "2026-08-09T00:00:00Z");
        when(service.search("G1", 0, 20))
                .thenReturn(new PageResult<>(0, 20, 1, List.of(hit)));

        mockMvc.perform(get("/api/v1/search").param("q", "G1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total").value(1))
                .andExpect(jsonPath("$.data.items[0].node_id").value("java-g1"))
                .andExpect(jsonPath("$.data.items[0].highlighted_title")
                        .value("[[G1]] 垃圾回收"))
                .andExpect(jsonPath("$.data.items[0].snippet")
                        .value("[[G1]] 使用 Region"))
                .andExpect(jsonPath("$.data.items[0].rank").value(-2.5));
    }

    @Test
    void returnsStableNotFoundError() throws Exception {
        when(service.document("missing")).thenThrow(new KnowledgeNotFoundException("missing"));

        mockMvc.perform(get("/api/v1/documents/missing"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.api_version").value("v1"))
                .andExpect(jsonPath("$.data.code").value("knowledge_not_found"));
    }

    @Test
    void rejectsOversizedSearchTermsBeforeTheyReachTheStore() throws Exception {
        mockMvc.perform(get("/api/v1/search").param("q", "x".repeat(201)))
                .andExpect(status().isBadRequest());

        mockMvc.perform(get("/api/v1/documents").param("query", "x".repeat(201)))
                .andExpect(status().isBadRequest());
    }
}
