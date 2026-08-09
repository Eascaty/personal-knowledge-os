package io.github.eascaty.knowledge.domain;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record TaxonomyNode(
        String id,
        @JsonProperty("parent_id") String parentId,
        String name,
        List<String> path,
        boolean locked,
        List<TaxonomyNode> children) {
}
