package io.github.eascaty.knowledge.domain;

import java.util.List;

public record PageResult<T>(
        int page,
        int size,
        long total,
        List<T> items) {
}
