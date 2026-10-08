# The listener as a service: docker build -t aimail-listener listener/
# Configuration comes from the environment (see .env.example); Pub/Sub uses the runtime's service
# account through Application Default Credentials, so no credentials.json or token.json is baked in.

FROM golang:1.26-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY *.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/listener .

FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app
COPY --from=build /out/listener /app/listener
# Probes reach the container's address, not its loopback.
ENV LISTENER_HEALTH_ADDR=0.0.0.0:8095
EXPOSE 8095
USER nonroot:nonroot
ENTRYPOINT ["/app/listener"]
