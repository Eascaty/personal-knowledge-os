package io.github.eascaty.knowledge.api;

import jakarta.validation.ConstraintViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class KnowledgeExceptionHandler {

    @ExceptionHandler(KnowledgeNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ApiResponse<ApiError> notFound(KnowledgeNotFoundException exception) {
        return ApiResponse.of(new ApiError("knowledge_not_found", exception.getMessage()));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<ApiError> invalidRequest(ConstraintViolationException exception) {
        return ApiResponse.of(new ApiError("invalid_request", exception.getMessage()));
    }

    @ExceptionHandler(KnowledgeStoreException.class)
    @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)
    public ApiResponse<ApiError> storeUnavailable(KnowledgeStoreException exception) {
        return ApiResponse.of(new ApiError("knowledge_store_unavailable", exception.getMessage()));
    }
}
