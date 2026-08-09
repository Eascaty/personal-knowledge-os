package io.github.eascaty.knowledge.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.github.eascaty.knowledge.config.KnowledgeProperties;
import io.github.eascaty.knowledge.domain.HealthStatus;
import io.github.eascaty.knowledge.domain.KnowledgeDocument;
import io.github.eascaty.knowledge.domain.PageResult;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.Statement;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class SqliteKnowledgeQueryRepositoryTest {

    @TempDir
    private Path tempDir;

    private Path database;
    private ObjectMapper objectMapper;
    private SqliteKnowledgeQueryRepository repository;

    @BeforeEach
    void setUp() throws Exception {
        database = tempDir.resolve("knowledge.sqlite3");
        objectMapper = new ObjectMapper().findAndRegisterModules();
        createDatabase();
        KnowledgeProperties properties = new KnowledgeProperties();
        properties.setDatabasePath(database);
        repository = new SqliteKnowledgeQueryRepository(properties, objectMapper);
    }

    @Test
    void reportsSchemaAndBuildsStrictTaxonomyTree() {
        HealthStatus health = repository.health();

        assertThat(health.status()).isEqualTo("UP");
        assertThat(health.schemaVersion()).isEqualTo(1);
        assertThat(repository.findTaxonomy()).singleElement().satisfies(root -> {
            assertThat(root.id()).isEqualTo("root");
            assertThat(root.children()).singleElement()
                    .satisfies(child -> assertThat(child.id()).isEqualTo("java-g1"));
        });
    }

    @Test
    void returnsOnlyPublicDocumentsAndSanitizesSource() throws Exception {
        PageResult<?> result = repository.findDocuments("G1", 0, 20);

        assertThat(result.total()).isEqualTo(1);
        assertThat(result.items()).hasSize(1);
        assertThat(repository.findDocument("doc-private")).isEmpty();

        KnowledgeDocument document = repository.findDocument("doc-public").orElseThrow();
        String responseJson = objectMapper.writeValueAsString(ApiResponseFixture.wrap(document));
        assertThat(document.relations()).hasSize(1);
        assertThat(responseJson)
                .contains("public.md")
                .doesNotContain("raw_path")
                .doesNotContain("/Users/example/private.md");
    }

    @Test
    void escapesSqlWildcardsInSearchTerms() {
        assertThat(repository.findDocuments("%", 0, 20).total()).isZero();
        assertThat(repository.findDocuments("_", 0, 20).total()).isZero();
    }

    private void createDatabase() throws Exception {
        try (Connection connection = DriverManager.getConnection("jdbc:sqlite:" + database);
             Statement statement = connection.createStatement()) {
            statement.executeUpdate("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)");
            statement.executeUpdate("INSERT INTO metadata VALUES ('schema_version', '1')");
            statement.executeUpdate("""
                    CREATE TABLE nodes (
                        id TEXT PRIMARY KEY, parent_id TEXT, name TEXT NOT NULL,
                        level INTEGER NOT NULL, path_json TEXT NOT NULL,
                        locked INTEGER NOT NULL, sort_order INTEGER NOT NULL, active INTEGER NOT NULL)
                    """);
            statement.executeUpdate("""
                    INSERT INTO nodes VALUES
                    ('root', NULL, '我的知识体系', 0, '[\"我的知识体系\"]', 1, 0, 1),
                    ('java-g1', 'root', 'G1', 1, '[\"我的知识体系\",\"G1\"]', 0, 0, 1)
                    """);
            statement.executeUpdate("""
                    CREATE TABLE sources (
                        id TEXT PRIMARY KEY, kind TEXT NOT NULL, origin TEXT NOT NULL,
                        original_name TEXT NOT NULL, raw_path TEXT NOT NULL,
                        sha256 TEXT NOT NULL)
                    """);
            statement.executeUpdate("""
                    INSERT INTO sources VALUES
                    ('source-public', 'markdown', '/Users/example/private.md', 'public.md', '/Users/example/private.md', 'abc123'),
                    ('source-private', 'markdown', '/Users/example/secret.md', 'secret.md', '/Users/example/secret.md', 'def456')
                    """);
            statement.executeUpdate("""
                    CREATE TABLE documents (
                        id TEXT PRIMARY KEY, source_id TEXT NOT NULL, title TEXT NOT NULL,
                        body TEXT NOT NULL, summary TEXT NOT NULL, tags_json TEXT NOT NULL,
                        visibility TEXT NOT NULL, updated_at TEXT NOT NULL)
                    """);
            statement.executeUpdate("""
                    INSERT INTO documents VALUES
                    ('doc-public', 'source-public', 'G1 垃圾回收', 'G1 使用 Region', '公开摘要', '[\"G1\"]', 'public', '2026-08-09T00:00:00Z'),
                    ('doc-private', 'source-private', '私密资料', '不可公开', '私密摘要', '[]', 'private', '2026-08-09T00:00:00Z')
                    """);
            statement.executeUpdate("CREATE TABLE placements (document_id TEXT PRIMARY KEY, node_id TEXT NOT NULL)");
            statement.executeUpdate("INSERT INTO placements VALUES ('doc-public', 'java-g1'), ('doc-private', 'java-g1')");
            statement.executeUpdate("""
                    CREATE TABLE relations (
                        id TEXT PRIMARY KEY, from_node_id TEXT NOT NULL, to_node_id TEXT NOT NULL,
                        relation_type TEXT NOT NULL, label TEXT NOT NULL,
                        document_id TEXT, confidence REAL NOT NULL)
                    """);
            statement.executeUpdate("""
                    INSERT INTO relations VALUES
                    ('relation-1', 'java-g1', 'root', 'belongs-to', '属于', 'doc-public', 1.0)
                    """);
        }
    }

    private record ApiResponseFixture(String api_version, Object data) {
        private static ApiResponseFixture wrap(Object data) {
            return new ApiResponseFixture("v1", data);
        }
    }
}
