FROM eclipse-temurin:21.0.11_10-jdk-alpine-3.23 AS build

WORKDIR /workspace
COPY apps/api/.mvn/ .mvn/
COPY apps/api/mvnw apps/api/pom.xml ./
COPY apps/api/src/ src/
RUN chmod 0755 mvnw \
    && ./mvnw --batch-mode -DskipTests clean package \
    && jar_path=$(find target -maxdepth 1 -type f \
        -name 'personal-knowledge-service-*.jar' \
        ! -name '*.jar.original') \
    && test -n "${jar_path}" \
    && test "$(printf '%s\n' "${jar_path}" | wc -l | tr -d ' ')" = "1" \
    && cp "${jar_path}" /workspace/service.jar

FROM eclipse-temurin:21.0.11_10-jre-alpine-3.23

RUN addgroup -S knowledge \
    && adduser -S -D -H -u 10001 -G knowledge knowledge

WORKDIR /app
COPY --from=build --chown=10001:10001 /workspace/service.jar /app/service.jar

ENV SERVER_ADDRESS=0.0.0.0 \
    PORT=8080 \
    KNOWLEDGE_DB_PATH=/data/knowledge.sqlite3 \
    JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0 -Djava.io.tmpdir=/tmp -Dorg.sqlite.tmpdir=/sqlite-native"

USER 10001:10001
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD wget -q -O - http://127.0.0.1:8080/actuator/health/readiness \
        | grep -q '"status":"UP"'

ENTRYPOINT ["java", "-jar", "/app/service.jar"]
