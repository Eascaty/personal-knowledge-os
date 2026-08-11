package io.github.eascaty.knowledge.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.eascaty.knowledge.config.KnowledgeProperties;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class SqliteSearchBenchmarkTest {

    private static final int DOCUMENT_COUNT = 2_000;
    private static final int MATCH_COUNT = 200;
    private static final int MEASURED_RUNS = 50;

    @TempDir
    private Path tempDir;

    @Test
    void searchesFixedChineseDatasetWithinRegressionBudget() throws Exception {
        Path database = tempDir.resolve("benchmark.sqlite3");
        createDatabase(database);
        KnowledgeProperties properties = new KnowledgeProperties();
        properties.setDatabasePath(database);
        SqliteKnowledgeQueryRepository repository = new SqliteKnowledgeQueryRepository(
                properties, new ObjectMapper().findAndRegisterModules());

        for (int warmup = 0; warmup < 10; warmup++) {
            assertThat(repository.searchDocuments("并发编程", 0, 20).total())
                    .isEqualTo(MATCH_COUNT);
        }
        List<Long> elapsedMicros = new ArrayList<>();
        for (int run = 0; run < MEASURED_RUNS; run++) {
            long started = System.nanoTime();
            var result = repository.searchDocuments("并发编程", 0, 20);
            elapsedMicros.add((System.nanoTime() - started) / 1_000);
            assertThat(result.total()).isEqualTo(MATCH_COUNT);
            assertThat(result.items()).hasSize(20);
        }
        Collections.sort(elapsedMicros);
        long medianMicros = percentile(elapsedMicros, 50);
        long p95Micros = percentile(elapsedMicros, 95);
        System.out.printf(
                "J2 FTS benchmark: docs=%d matches=%d runs=%d median=%.3fms p95=%.3fms%n",
                DOCUMENT_COUNT,
                MATCH_COUNT,
                MEASURED_RUNS,
                medianMicros / 1_000.0,
                p95Micros / 1_000.0);
        assertThat(p95Micros).isLessThan(1_000_000L);
    }

    private long percentile(List<Long> sorted, int percentile) {
        int index = Math.min(
                sorted.size() - 1,
                Math.max(0, (int) Math.ceil(sorted.size() * percentile / 100.0) - 1));
        return sorted.get(index);
    }

    private void createDatabase(Path database) throws Exception {
        try (Connection connection = DriverManager.getConnection("jdbc:sqlite:" + database)) {
            connection.setAutoCommit(false);
            try (Statement statement = connection.createStatement()) {
                statement.executeUpdate(
                        "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)");
                statement.executeUpdate("INSERT INTO metadata VALUES ('schema_version', '1')");
                statement.executeUpdate("INSERT INTO metadata VALUES ('fts_tokenizer', 'trigram')");
                statement.executeUpdate("""
                        CREATE TABLE nodes (
                            id TEXT PRIMARY KEY, parent_id TEXT, name TEXT NOT NULL,
                            level INTEGER NOT NULL, path_json TEXT NOT NULL,
                            locked INTEGER NOT NULL, sort_order INTEGER NOT NULL,
                            active INTEGER NOT NULL)
                        """);
                statement.executeUpdate("""
                        INSERT INTO nodes VALUES
                        ('java-concurrency', NULL, '并发编程', 0,
                         '["技术","Java开发","并发编程"]', 0, 0, 1)
                        """);
                statement.executeUpdate("""
                        CREATE TABLE documents (
                            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, title TEXT NOT NULL,
                            body TEXT NOT NULL, summary TEXT NOT NULL, tags_json TEXT NOT NULL,
                            visibility TEXT NOT NULL, updated_at TEXT NOT NULL)
                        """);
                statement.executeUpdate(
                        "CREATE TABLE placements (document_id TEXT PRIMARY KEY, node_id TEXT NOT NULL)");
                statement.executeUpdate("""
                        CREATE VIRTUAL TABLE documents_fts USING fts5(
                            document_id UNINDEXED, title, body, tags, taxonomy_path,
                            tokenize='trigram')
                        """);
            }
            try (PreparedStatement document = connection.prepareStatement("""
                         INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, 'public', ?)
                         """);
                 PreparedStatement placement = connection.prepareStatement(
                         "INSERT INTO placements VALUES (?, 'java-concurrency')");
                 PreparedStatement fts = connection.prepareStatement("""
                         INSERT INTO documents_fts VALUES (?, ?, ?, ?, ?)
                         """)) {
                for (int index = 0; index < DOCUMENT_COUNT; index++) {
                    boolean matches = index % 10 == 0;
                    String id = "benchmark-" + index;
                    String title = matches && index % 20 == 0
                            ? "并发编程实战 " + index
                            : "Java 工程笔记 " + index;
                    String body = matches && index % 20 != 0
                            ? "本文记录并发编程中的线程池、锁与性能诊断。"
                            : "本文记录一般 Java 工程实践与测试策略。";
                    document.setString(1, id);
                    document.setString(2, "source-" + index);
                    document.setString(3, title);
                    document.setString(4, body);
                    document.setString(5, "固定基准资料 " + index);
                    document.setString(6, matches ? "[\"并发编程\"]" : "[\"Java\"]");
                    document.setString(7, "2026-08-12T00:00:00Z");
                    document.addBatch();
                    placement.setString(1, id);
                    placement.addBatch();
                    fts.setString(1, id);
                    fts.setString(2, title);
                    fts.setString(3, body);
                    fts.setString(4, matches ? "并发编程" : "Java");
                    fts.setString(5, "技术 / Java开发 / 工程实践");
                    fts.addBatch();
                }
                document.executeBatch();
                placement.executeBatch();
                fts.executeBatch();
            }
            connection.commit();
        }
    }
}
