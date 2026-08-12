package io.github.eascaty.knowledge.observability;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import io.github.eascaty.knowledge.domain.HealthStatus;
import io.github.eascaty.knowledge.repository.KnowledgeQueryRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.actuate.health.Status;

@ExtendWith(MockitoExtension.class)
class KnowledgeDatabaseHealthIndicatorTest {

    @Mock
    private KnowledgeQueryRepository repository;

    @InjectMocks
    private KnowledgeDatabaseHealthIndicator indicator;

    @Test
    void reportsReadyWhenSchemaV1DatabaseIsReadable() {
        when(repository.health()).thenReturn(
                new HealthStatus("UP", "personal-knowledge-service", "available", 1));

        assertThat(indicator.health()).satisfies(health -> {
            assertThat(health.getStatus()).isEqualTo(Status.UP);
            assertThat(health.getDetails())
                    .containsEntry("database", "available")
                    .containsEntry("schemaVersion", 1);
        });
    }

    @Test
    void reportsNotReadyWhenDatabaseCannotBeRead() {
        when(repository.health()).thenReturn(
                new HealthStatus("DOWN", "personal-knowledge-service", "unavailable", null));

        assertThat(indicator.health()).satisfies(health -> {
            assertThat(health.getStatus()).isEqualTo(Status.DOWN);
            assertThat(health.getDetails()).containsEntry("database", "unavailable");
        });
    }
}
