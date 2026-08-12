package io.github.eascaty.knowledge.importer;

public class KnowledgeImportException extends RuntimeException {

    public KnowledgeImportException(String message) {
        super(message);
    }

    public KnowledgeImportException(String message, Throwable cause) {
        super(message, cause);
    }
}
