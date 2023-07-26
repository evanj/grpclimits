BUILD_DIR:=build
PROTOC:=$(BUILD_DIR)/bin/protoc
PROTOC_GEN_GO:=$(BUILD_DIR)/protoc-gen-go
PROTOC_GEN_GO_GRPC:=$(BUILD_DIR)/protoc-gen-go-grpc

all: $(BUILD_DIR)/.gocheck_stamp $(BUILD_DIR)/venv $(BUILD_DIR)/.pythoncheck

$(BUILD_DIR)/.gocheck_stamp: $(wildcard **/*.go) helloworld/helloworld.pb.go | $(BUILD_DIR)
	go test ./...
	go vet ./...
	staticcheck ./...
	go mod tidy
	touch $@

$(BUILD_DIR)/venv: python/requirements.txt python/requirements_test.txt python/requirements_venv.txt
	rm -rf $@
	python3 -m venv $@
	# update pip/setuptools before installing the other requirements
	$@/bin/pip install -r python/requirements_venv.txt
	$@/bin/pip install -r python/requirements.txt -r python/requirements_test.txt

# recursive wildcard function from
# https://blog.jgc.org/2011/07/gnu-make-recursive-wildcard-function.html
rwildcard=$(foreach d,$(wildcard $1*),$(call rwildcard,$d/,$2) $(filter $(subst *,%,$2),$d))

PYTHON_FILES:=$(filter-out python/helloworld_pb2%.py, $(call rwildcard,python,*.py))
$(BUILD_DIR)/.pythoncheck: $(PYTHON_FILES) python/helloworld_pb2.py | $(BUILD_DIR)/venv
	$(BUILD_DIR)/venv/bin/black --line-length=100 $(PYTHON_FILES)
	PYTHONPATH=python $(BUILD_DIR)/venv/bin/mypy --follow-imports=silent --strict --allow-untyped-calls $(PYTHON_FILES)
	PYTHONPATH=python $(BUILD_DIR)/venv/bin/pytest --log-level=debug
	touch $@

helloworld/helloworld.pb.go: java/errorlimitserver/src/main/proto/helloworld.proto $(PROTOC) $(PROTOC_GEN_GO) $(PROTOC_GEN_GO_GRPC)
	$(PROTOC) --plugin=$(PROTOC_GEN_GO) --plugin=$(PROTOC_GEN_GO_GRPC) \
		--go_out=. --go_opt=Mjava/errorlimitserver/src/main/proto/helloworld.proto=./helloworld \
		--go-grpc_out=. --go-grpc_opt=Mjava/errorlimitserver/src/main/proto/helloworld.proto=./helloworld \
		$<

python/helloworld_pb2.py: java/errorlimitserver/src/main/proto/helloworld.proto $(BUILD_DIR)/venv
	$(BUILD_DIR)/venv/bin/python3 -m grpc_tools.protoc --proto_path=java/errorlimitserver/src/main/proto \
		--python_out=python \
		--pyi_out=python \
		--grpc_python_out=python \
		$<

# download protoc to a temporary tools directory
$(PROTOC): $(BUILD_DIR)/getprotoc | $(BUILD_DIR)
	$(BUILD_DIR)/getprotoc --outputDir=$(BUILD_DIR)

$(BUILD_DIR)/getprotoc: | $(BUILD_DIR)
	GOBIN=$(realpath $(BUILD_DIR)) go install github.com/evanj/hacks/getprotoc@latest

# go install uses the version of protoc-gen-go specified by go.mod ... I think
$(PROTOC_GEN_GO): go.mod | $(BUILD_DIR)
	GOBIN=$(realpath $(BUILD_DIR)) go install google.golang.org/protobuf/cmd/protoc-gen-go

# manually specified version since we don't import this from code anywhere
# TODO: Import this from some tool so it gets updated with go get?
$(PROTOC_GEN_GO_GRPC): go.mod | $(BUILD_DIR)
	GOBIN=$(realpath $(BUILD_DIR)) go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.3.0

$(BUILD_DIR):
	mkdir -p $@

clean:
	$(RM) -r $(BUILD_DIR) python/__pycache__ helloworld/*.pb.go python/*_pb2*.py*

docker:
	docker build . --tag=gcr.io/networkping/grpclimitsserver:$(shell date '+%Y%m%d')-$(shell git rev-parse --short=10 HEAD)
	docker run --rm -ti gcr.io/networkping/grpclimitsserver:$(shell date '+%Y%m%d')-$(shell git rev-parse --short=10 HEAD) --help
	docker build -f Dockerfile.pythonclient . --tag=gcr.io/networkping/pythonclient:$(shell date '+%Y%m%d')-$(shell git rev-parse --short=10 HEAD)
	docker run --rm -ti gcr.io/networkping/pythonclient:$(shell date '+%Y%m%d')-$(shell git rev-parse --short=10 HEAD) --help
	echo "SUCCESS"
