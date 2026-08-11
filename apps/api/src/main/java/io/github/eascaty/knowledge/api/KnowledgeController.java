package io.github.eascaty.knowledge.api;

import io.github.eascaty.knowledge.domain.HealthStatus;
import io.github.eascaty.knowledge.domain.KnowledgeDocument;
import io.github.eascaty.knowledge.domain.KnowledgeDocumentSummary;
import io.github.eascaty.knowledge.domain.PageResult;
import io.github.eascaty.knowledge.domain.TaxonomyNode;
import io.github.eascaty.knowledge.service.KnowledgeQueryService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import java.util.List;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1")
public class KnowledgeController {

    private final KnowledgeQueryService service;

    public KnowledgeController(KnowledgeQueryService service) {
        this.service = service;
    }

    @GetMapping("/health")
    public ApiResponse<HealthStatus> health() {
        return ApiResponse.of(service.health());
    }

    @GetMapping("/taxonomy")
    public ApiResponse<List<TaxonomyNode>> taxonomy() {
        return ApiResponse.of(service.taxonomy());
    }

    @GetMapping("/documents")
    public ApiResponse<PageResult<KnowledgeDocumentSummary>> documents(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return ApiResponse.of(service.documents(query, page, size));
    }

    @GetMapping("/documents/{id}")
    public ApiResponse<KnowledgeDocument> document(@PathVariable @NotBlank String id) {
        return ApiResponse.of(service.document(id));
    }

    @GetMapping("/search")
    public ApiResponse<PageResult<KnowledgeDocumentSummary>> search(
            @RequestParam @NotBlank String q,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return ApiResponse.of(service.documents(q, page, size));
    }
}
