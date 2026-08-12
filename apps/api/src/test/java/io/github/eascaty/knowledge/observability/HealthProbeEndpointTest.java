package io.github.eascaty.knowledge.observability;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import io.github.eascaty.knowledge.domain.HealthStatus;
import io.github.eascaty.knowledge.repository.KnowledgeQueryRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
class HealthProbeEndpointTest {

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private KnowledgeQueryRepository repository;

    @Test
    void exposesLivenessAndDatabaseBackedReadiness() {
        when(repository.health()).thenReturn(
                new HealthStatus("UP", "personal-knowledge-service", "available", 1));

        ResponseEntity<String> liveness = restTemplate.getForEntity(
                "/actuator/health/liveness", String.class);
        ResponseEntity<String> readiness = restTemplate.getForEntity(
                "/actuator/health/readiness", String.class);

        assertThat(liveness.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(liveness.getBody()).contains("\"status\":\"UP\"");
        assertThat(readiness.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(readiness.getBody()).contains("\"status\":\"UP\"");
    }

    @Test
    void returnsServiceUnavailableWhenDatabaseIsNotReady() {
        when(repository.health()).thenReturn(
                new HealthStatus("DOWN", "personal-knowledge-service", "unavailable", null));

        ResponseEntity<String> liveness = restTemplate.getForEntity(
                "/actuator/health/liveness", String.class);
        ResponseEntity<String> readiness = restTemplate.getForEntity(
                "/actuator/health/readiness", String.class);

        assertThat(liveness.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(liveness.getBody()).contains("\"status\":\"UP\"");
        assertThat(readiness.getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
        assertThat(readiness.getBody()).contains("\"status\":\"DOWN\"");
    }

    @Test
    void doesNotExposeActuatorDiscoveryOrSensitiveEndpoints() {
        assertThat(restTemplate.getForEntity("/actuator", String.class).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(restTemplate.getForEntity("/actuator/env", String.class).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(restTemplate.getForEntity("/actuator/configprops", String.class).getStatusCode())
                .isEqualTo(HttpStatus.NOT_FOUND);
    }

    @TestConfiguration
    static class RepositoryConfiguration {

        @Bean
        @Primary
        KnowledgeQueryRepository testKnowledgeQueryRepository() {
            return org.mockito.Mockito.mock(KnowledgeQueryRepository.class);
        }
    }
}
