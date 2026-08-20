# Cantaloupe + Grok build of the iiif_stage service.
#
# Replaces RAIS/OpenJPEG with Cantaloupe/Grok for JP2 decoding, which is
# roughly 6-8x faster for large images (see project history/benchmarks).
# Keeps the same port (12415) and image mount (/var/local/images) as RAIS,
# so nothing else in the stack needs to change.
#
# Cantaloupe is built from source at a specific commit rather than the
# v5.0.7 release: 5.0.7 (and everything before it) has a bug where
# OperationList.applyNonEndpointMutations() runs twice per request and
# throws "IllegalStateException: Instance is frozen" on every image
# request (not just info.json). Fixed by upstream PR #949
# (cantaloupe-project/cantaloupe), not yet in a tagged release.
# Switch this back to a release zip once a version after 5.0.7 ships.
ARG CANTALOUPE_COMMIT=613de29917707f45726b15df8896d3a6545a273c

# Grok's prebuilt Linux binaries need a glibc/libstdc++ newer than Ubuntu
# 22.04 ("jammy") ships - grk_decompress fails to even start on jammy
# (GLIBC_2.38/2.39, GLIBCXX_3.4.31/3.4.32 not found). Ubuntu 24.04
# ("noble") has what it needs. If eclipse-temurin ever drops the -noble
# tag, either pin an older Grok release or build Grok from source instead.

FROM maven:3.9-eclipse-temurin-21 AS cantaloupe-build
ARG CANTALOUPE_COMMIT

RUN git clone https://github.com/cantaloupe-project/cantaloupe.git /src \
    && cd /src && git checkout "${CANTALOUPE_COMMIT}"

WORKDIR /src
RUN mvn -B -DskipTests -q package \
    && cp target/cantaloupe-*.jar /cantaloupe.jar

# ---------------------------------------------------------------------------

FROM eclipse-temurin:21-jre-noble AS fetch

ARG GROK_VERSION=v20.3.11

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /fetch

RUN curl -sL -o grok.zip \
    "https://github.com/GrokImageCompression/grok/releases/download/${GROK_VERSION}/grok-ubuntu-latest.zip" \
    && unzip -q grok.zip \
    && mv grok-ubuntu-latest grok

# ---------------------------------------------------------------------------

FROM eclipse-temurin:21-jre-noble

RUN groupadd -r cantaloupe && useradd -r -g cantaloupe cantaloupe

# Grok binaries + shared libs (only what GrokProcessor actually needs -
# see https://cantaloupe-project.github.io/manual/5.0/processors.html)
COPY --from=fetch /fetch/grok/bin/grk_decompress /opt/grok/bin/grk_decompress
COPY --from=fetch /fetch/grok/bin/grk_dump /opt/grok/bin/grk_dump
COPY --from=fetch /fetch/grok/lib/libgrokj2k.so* /opt/grok/lib/
COPY --from=fetch /fetch/grok/lib/libgrokj2kcodec.so* /opt/grok/lib/
ENV LD_LIBRARY_PATH=/opt/grok/lib

COPY --from=cantaloupe-build /cantaloupe.jar /opt/cantaloupe/cantaloupe.jar
COPY cantaloupe.properties /etc/cantaloupe/cantaloupe.properties

RUN mkdir -p /var/cache/cantaloupe && chown -R cantaloupe:cantaloupe /var/cache/cantaloupe

USER cantaloupe
EXPOSE 12415

ENTRYPOINT ["java", "-Dcantaloupe.config=/etc/cantaloupe/cantaloupe.properties", "-jar", "/opt/cantaloupe/cantaloupe.jar"]
