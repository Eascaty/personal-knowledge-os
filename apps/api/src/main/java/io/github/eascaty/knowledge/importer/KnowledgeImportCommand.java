package io.github.eascaty.knowledge.importer;

import java.io.PrintStream;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public final class KnowledgeImportCommand {

    private KnowledgeImportCommand() {
    }

    public static void main(String[] arguments) {
        int exitCode = run(arguments, System.out, System.err);
        if (exitCode != 0) {
            System.exit(exitCode);
        }
    }

    static int run(String[] arguments, PrintStream output, PrintStream error) {
        try {
            Options options = Options.parse(arguments);
            SqliteKnowledgeImportService service = new SqliteKnowledgeImportService(
                    options.projectRoot(), options.database(), options.rawRoot(),
                    options.maximumFileMegabytes(), options.maximumAttempts());
            for (Path source : options.sources()) {
                KnowledgeImportResult result = service.importFile(source);
                output.println(toJson(result));
            }
            return 0;
        } catch (KnowledgeImportException exception) {
            error.println("Java 导入失败: " + exception.getMessage());
            return 2;
        }
    }

    static String toJson(KnowledgeImportResult result) {
        return "{"
                + "\"source_id\":\"" + escape(result.sourceId()) + "\","
                + "\"sha256\":\"" + escape(result.sha256()) + "\","
                + "\"original_name\":\"" + escape(result.originalName()) + "\","
                + "\"raw_path\":\"" + escape(result.rawPath()) + "\","
                + "\"duplicate\":" + result.duplicate()
                + "}";
    }

    private static String escape(String value) {
        StringBuilder escaped = new StringBuilder();
        for (int index = 0; index < value.length(); index++) {
            char character = value.charAt(index);
            switch (character) {
                case '\\' -> escaped.append("\\\\");
                case '"' -> escaped.append("\\\"");
                case '\n' -> escaped.append("\\n");
                case '\r' -> escaped.append("\\r");
                case '\t' -> escaped.append("\\t");
                default -> {
                    if (character < 0x20) {
                        escaped.append(String.format("\\u%04x", (int) character));
                    } else {
                        escaped.append(character);
                    }
                }
            }
        }
        return escaped.toString();
    }

    private record Options(
            Path projectRoot,
            Path database,
            Path rawRoot,
            int maximumFileMegabytes,
            int maximumAttempts,
            List<Path> sources) {

        private static Options parse(String[] arguments) {
            Path projectRoot = null;
            Path database = null;
            Path rawRoot = null;
            int maximumFileMegabytes = 512;
            int maximumAttempts = 3;
            List<Path> sources = new ArrayList<>();
            for (int index = 0; index < arguments.length; index++) {
                String argument = arguments[index];
                switch (argument) {
                    case "--project-root" -> projectRoot = Path.of(value(arguments, ++index, argument));
                    case "--database" -> database = Path.of(value(arguments, ++index, argument));
                    case "--raw-root" -> rawRoot = Path.of(value(arguments, ++index, argument));
                    case "--max-file-mb" -> maximumFileMegabytes = positiveInteger(
                            value(arguments, ++index, argument), argument);
                    case "--max-attempts" -> maximumAttempts = positiveInteger(
                            value(arguments, ++index, argument), argument);
                    default -> {
                        if (argument.startsWith("--")) {
                            throw new KnowledgeImportException("未知参数: " + argument);
                        }
                        sources.add(Path.of(argument));
                    }
                }
            }
            if (projectRoot == null || database == null || rawRoot == null) {
                throw new KnowledgeImportException(
                        "缺少 --project-root、--database 或 --raw-root");
            }
            if (sources.isEmpty()) {
                throw new KnowledgeImportException("至少提供一个待导入文件");
            }
            return new Options(
                    projectRoot, database, rawRoot, maximumFileMegabytes,
                    maximumAttempts, List.copyOf(sources));
        }

        private static String value(String[] arguments, int index, String option) {
            if (index >= arguments.length) {
                throw new KnowledgeImportException("参数缺少值: " + option);
            }
            return arguments[index];
        }

        private static int positiveInteger(String value, String option) {
            try {
                int parsed = Integer.parseInt(value);
                if (parsed < 1) {
                    throw new NumberFormatException();
                }
                return parsed;
            } catch (NumberFormatException exception) {
                throw new KnowledgeImportException(option + " 必须是正整数");
            }
        }
    }
}
