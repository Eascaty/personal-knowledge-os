package io.github.eascaty.knowledge.repository;

import io.github.eascaty.knowledge.domain.HealthStatus;
import io.github.eascaty.knowledge.domain.KnowledgeDocument;
import io.github.eascaty.knowledge.domain.KnowledgeDocumentSummary;
import io.github.eascaty.knowledge.domain.KnowledgeSearchHit;
import io.github.eascaty.knowledge.domain.PageResult;
import io.github.eascaty.knowledge.domain.TaxonomyNode;
import java.util.List;
import java.util.Optional;

public interface KnowledgeQueryRepository {

    HealthStatus health();

    List<TaxonomyNode> findTaxonomy();

    PageResult<KnowledgeDocumentSummary> findDocuments(String query, int page, int size);

    PageResult<KnowledgeSearchHit> searchDocuments(String query, int page, int size);

    Optional<KnowledgeDocument> findDocument(String id);
}
