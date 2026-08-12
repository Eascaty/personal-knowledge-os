package io.github.eascaty.knowledge.observability;

import io.github.eascaty.knowledge.domain.HealthStatus;
import io.github.eascaty.knowledge.repository.KnowledgeQueryRepository;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

@Component("knowledgeDatabase")
public class KnowledgeDatabaseHealthIndicator implements HealthIndicator {

    private final KnowledgeQueryRepository repository;

    public KnowledgeDatabaseHealthIndicator(KnowledgeQueryRepository repository) {
        this.repository = repository;
    }

    @Override
    public Health health() {
        HealthStatus status = repository.health();
        Health.Builder health = "UP".equals(status.status())
                ? Health.up()
                : Health.down();
        health.withDetail("database", status.database());
        if (status.schemaVersion() != null) {
            health.withDetail("schemaVersion", status.schemaVersion());
        }
        return health.build();
    }
}
