package io.github.eascaty.knowledge.api;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ApiResponse<T>(
        @JsonProperty("api_version") String apiVersion,
        T data) {

    public static <T> ApiResponse<T> of(T data) {
        return new ApiResponse<>("v1", data);
    }
}
