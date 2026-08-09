package io.github.eascaty.knowledge.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

import io.github.eascaty.knowledge.api.KnowledgeNotFoundException;
import io.github.eascaty.knowledge.domain.HealthStatus;
import io.github.eascaty.knowledge.domain.KnowledgeDocument;
import io.github.eascaty.knowledge.domain.KnowledgeDocumentSummary;
import io.github.eascaty.knowledge.domain.PageResult;
import io.github.eascaty.knowledge.repository.KnowledgeQueryRepository;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class KnowledgeQueryServiceTest {

    @Mock
    private KnowledgeQueryRepository repository;

    @InjectMocks
    private KnowledgeQueryService service;

    @Test
    void delegatesReadModelsToRepository() {
        HealthStatus health = new HealthStatus("UP", "knowledge", "available", 1);
        PageResult<KnowledgeDocumentSummary> page = new PageResult<>(0, 20, 0, List.of());
        when(repository.health()).thenReturn(health);
        when(repository.findTaxonomy()).thenReturn(List.of());
        when(repository.findDocuments("G1", 0, 20)).thenReturn(page);

        assertThat(service.health()).isSameAs(health);
        assertThat(service.taxonomy()).isEmpty();
        assertThat(service.documents("G1", 0, 20)).isSameAs(page);
    }

    @Test
    void returnsExistingDocumentAndMapsMissingDocumentToDomainError() {
        KnowledgeDocument document = new KnowledgeDocument(
                "doc", "标题", "正文", "摘要", List.of(), "root", List.of(), "", null, List.of());
        when(repository.findDocument("doc")).thenReturn(Optional.of(document));
        when(repository.findDocument("missing")).thenReturn(Optional.empty());

        assertThat(service.document("doc")).isSameAs(document);
        assertThatThrownBy(() -> service.document("missing"))
                .isInstanceOf(KnowledgeNotFoundException.class);
    }
}
