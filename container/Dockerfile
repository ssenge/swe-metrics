# swe-metrics with every tool at the versions in container/tools.lock. Build from the repository root:
#   docker build -f container/Dockerfile -t swe-metrics .
# Run (the target is mounted read-only):
#   docker run --rm -v "$PWD:/work:ro" swe-metrics measure /work
# Base images are pinned by digest (multi-arch indexes; arm64 and amd64).
FROM eclipse-temurin:21-jdk@sha256:3e3c176ffed168beb42c607be9bc1639b466cf00261a0fb04425562c9d0c5c2b AS jdk

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates xz-utils unzip \
 && rm -rf /var/lib/apt/lists/*
COPY --from=jdk /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk \
    PATH=/opt/java/openjdk/bin:/opt/node/bin:$PATH \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY container/tools.lock container/install-tools.sh container/check-tools.py /opt/swe-metrics/
RUN /opt/swe-metrics/install-tools.sh /opt/swe-metrics/tools.lock

COPY pyproject.toml README.md /src/
COPY swe_metrics /src/swe_metrics
RUN pip install --no-cache-dir /src && rm -rf /src \
 && python /opt/swe-metrics/check-tools.py /opt/swe-metrics/tools.lock

RUN useradd --create-home swe
USER swe
WORKDIR /work
ENTRYPOINT ["swe-metrics"]
CMD ["--help"]
