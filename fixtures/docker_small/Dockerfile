# Multi-stage build with known hadolint findings and base images (see expected.json).
ARG JAVA_VERSION=21
FROM maven:3.9-eclipse-temurin-${JAVA_VERSION} AS build
WORKDIR /src
COPY . .
RUN apt-get update && apt-get install -y curl
RUN cd app && mvn -q package

FROM eclipse-temurin:${JAVA_VERSION}-jre
COPY --from=build /src/app/target/app.jar /app.jar
EXPOSE 8080
CMD java -jar /app.jar
