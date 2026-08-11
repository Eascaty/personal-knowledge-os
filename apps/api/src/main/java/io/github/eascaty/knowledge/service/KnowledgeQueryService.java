package io.github.eascaty.knowledge.service;

import io.github.eascaty.knowledge.api.KnowledgeNotFoundException;
import io.github.eascaty.knowledge.domain.HealthStatus;
import io.github.eascaty.knowledge.domain.KnowledgeDocument;
import io.github.eascaty.knowledge.domain.KnowledgeDocumentSummary;
import io.github.eascaty.knowledge.domain.PageResult;
import io.github.eascaty.knowledge.domain.TaxonomyNode;
import io.github.eascaty.knowledge.repository.KnowledgeQueryRepository;
import java.util.List;
import org.springframework.stereotype.Service;

@Service
public class KnowledgeQueryService {

    private final KnowledgeQueryRepository repository;

    public KnowledgeQueryService(KnowledgeQueryRepository repository) {
        this.repository = repository;
    }

    public HealthStatus health() {
        return repository.health();
    }

    public List<TaxonomyNode> taxonomy() {
        return repository.findTaxonomy();
    }

    public PageResult<KnowledgeDocumentSummary> documents(String query, int page, int size) {
        return repository.findDocuments(query, page, size);
    }

    public KnowledgeDocument document(String id) {
        return repository.findDocument(id)
                .orElseThrow(() -> new KnowledgeNotFoundException(id));
    }
}
