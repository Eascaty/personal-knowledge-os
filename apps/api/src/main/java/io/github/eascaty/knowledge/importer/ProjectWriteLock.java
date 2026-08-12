package io.github.eascaty.knowledge.importer;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermission;
import java.time.Instant;
import java.util.Set;
import java.util.UUID;

final class ProjectWriteLock implements AutoCloseable {

    private static final Set<PosixFilePermission> OWNER_DIRECTORY = Set.of(
            PosixFilePermission.OWNER_READ,
            PosixFilePermission.OWNER_WRITE,
            PosixFilePermission.OWNER_EXECUTE);
    private static final Set<PosixFilePermission> OWNER_FILE = Set.of(
            PosixFilePermission.OWNER_READ,
            PosixFilePermission.OWNER_WRITE);

    private final FileChannel channel;
    private final FileLock lock;

    private ProjectWriteLock(FileChannel channel, FileLock lock) {
        this.channel = channel;
        this.lock = lock;
    }

    static ProjectWriteLock acquire(Path projectRoot) {
        Path lockPath = projectRoot.resolve(
                "workspace/data/state/knowledge-os.lock").normalize();
        FileChannel channel = null;
        try {
            Files.createDirectories(lockPath.getParent());
            setPermissions(lockPath.getParent(), OWNER_DIRECTORY);
            channel = FileChannel.open(
                    lockPath,
                    StandardOpenOption.CREATE,
                    StandardOpenOption.READ,
                    StandardOpenOption.WRITE);
            setPermissions(lockPath, OWNER_FILE);
            FileLock lock;
            try {
                lock = channel.tryLock();
            } catch (OverlappingFileLockException exception) {
                lock = null;
            }
            if (lock == null) {
                channel.close();
                throw new KnowledgeImportException("知识工程正在被其他写入任务占用");
            }
            writeMetadata(channel);
            return new ProjectWriteLock(channel, lock);
        } catch (IOException exception) {
            closeQuietly(channel);
            throw new KnowledgeImportException("无法获取知识工程写入锁", exception);
        }
    }

    private static void writeMetadata(FileChannel channel) throws IOException {
        String metadata = "{"
                + "\"acquired_at\":\"" + Instant.now() + "\","
                + "\"pid\":" + ProcessHandle.current().pid() + ","
                + "\"purpose\":\"java-import\","
                + "\"schema_version\":1,"
                + "\"token\":\"" + UUID.randomUUID().toString().replace("-", "") + "\""
                + "}\n";
        channel.truncate(0);
        channel.position(0);
        ByteBuffer buffer = StandardCharsets.UTF_8.encode(metadata);
        while (buffer.hasRemaining()) {
            channel.write(buffer);
        }
        channel.force(true);
    }

    private static void setPermissions(Path path, Set<PosixFilePermission> permissions) {
        try {
            Files.setPosixFilePermissions(path, permissions);
        } catch (UnsupportedOperationException | IOException ignored) {
            // Windows does not expose POSIX permissions; the project lock still works.
        }
    }

    private static void closeQuietly(FileChannel channel) {
        if (channel != null) {
            try {
                channel.close();
            } catch (IOException ignored) {
                // Preserve the original acquisition failure.
            }
        }
    }

    @Override
    public void close() {
        try {
            lock.release();
        } catch (IOException exception) {
            throw new KnowledgeImportException("无法释放知识工程写入锁", exception);
        } finally {
            closeQuietly(channel);
        }
    }
}
