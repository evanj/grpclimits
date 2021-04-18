# Go build image: separate downloading dependencies from build for incremental builds
FROM golang:1.16.3-buster AS go_dep_downloader
WORKDIR concurrentlimit
COPY go.mod .
COPY go.sum .
RUN go mod download -x

# Go build image: separate downloading dependencies from build for incremental builds
FROM go_dep_downloader AS go_builder
COPY . .
# build without CGO so we have a static executable
RUN CGO_ENABLED=0 go install -v ./grpclimitsserver

# grpclimitsserver
FROM gcr.io/distroless/static-debian10:nonroot as grpclimitsserver
COPY --from=go_builder /go/bin/grpclimitsserver /
ENTRYPOINT ["/grpclimitsserver"]
CMD ["--addr=:8080"]
EXPOSE 8080
