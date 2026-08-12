package io.github.eascaty.knowledge.importer;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class KnowledgeImportCommandTest {

    @TempDir
    private Path tempDir;

    @Test
    void returnsUsageErrorForMissingRequiredArguments() throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        ByteArrayOutputStream error = new ByteArrayOutputStream();

        int exitCode = KnowledgeImportCommand.run(
                new String[] {},
                new PrintStream(output, true, StandardCharsets.UTF_8),
                new PrintStream(error, true, StandardCharsets.UTF_8));

        assertThat(exitCode).isEqualTo(2);
        assertThat(output.toString(StandardCharsets.UTF_8)).isEmpty();
        assertThat(error.toString(StandardCharsets.UTF_8))
                .contains("Java 导入失败")
                .contains("缺少");
    }

    @Test
    void validatesUnknownMissingAndNumericOptions() throws Exception {
        assertUsageError("未知参数", "--unknown");
        assertUsageError("参数缺少值", "--project-root");
        assertUsageError("必须是正整数", "--max-file-mb", "0");
        assertUsageError("必须是正整数", "--max-attempts", "not-a-number");
    }

    @Test
    void requiresAtLeastOneSourceAfterValidConfiguration() throws Exception {
        assertUsageError(
                "至少提供一个待导入文件",
                "--project-root", tempDir.toString(),
                "--database", tempDir.resolve("knowledge.sqlite3").toString(),
                "--raw-root", tempDir.resolve("raw").toString());
    }

    @Test
    void emitsEscapedJsonForSuccessfulResult() {
        KnowledgeImportResult result = new KnowledgeImportResult(
                "sha256-abc", "abc", "quote\"line\n.md",
                "workspace\\raw\tfile.md", false);

        assertThat(KnowledgeImportCommand.toJson(result))
                .isEqualTo("{\"source_id\":\"sha256-abc\",\"sha256\":\"abc\","
                        + "\"original_name\":\"quote\\\"line\\n.md\","
                        + "\"raw_path\":\"workspace\\\\raw\\tfile.md\","
                        + "\"duplicate\":false}");
    }

    @Test
    void reportsMissingInputFromConfiguredCommand() throws Exception {
        Path database = tempDir.resolve("knowledge.sqlite3");
        Files.writeString(database, "not sqlite", StandardCharsets.UTF_8);
        assertUsageError(
                "不是普通文件",
                "--project-root", tempDir.toString(),
                "--database", database.toString(),
                "--raw-root", tempDir.resolve("raw").toString(),
                tempDir.resolve("missing.md").toString());
    }

    private void assertUsageError(String expected, String... arguments) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        ByteArrayOutputStream error = new ByteArrayOutputStream();
        int exitCode = KnowledgeImportCommand.run(
                arguments,
                new PrintStream(output, true, StandardCharsets.UTF_8),
                new PrintStream(error, true, StandardCharsets.UTF_8));

        assertThat(exitCode).isEqualTo(2);
        assertThat(output.toString(StandardCharsets.UTF_8)).isEmpty();
        assertThat(error.toString(StandardCharsets.UTF_8)).contains(expected);
    }
}
