BUILD_DIR:=build
PROTOC:=$(BUILD_DIR)/bin/protoc
PROTOC_GEN_GO:=$(BUILD_DIR)/protoc-gen-go

all: $(BUILD_DIR)/.gocheck_stamp $(BUILD_DIR)/venv $(BUILD_DIR)/.pythoncheck

$(BUILD_DIR)/.gocheck_stamp: $(wildcard **/*.go) helloworld/helloworld.pb.go | $(BUILD_DIR)
	go test ./...
	go vet ./...
	golint ./...
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

helloworld/helloworld.pb.go: java/errorlimitserver/src/main/proto/helloworld.proto $(PROTOC) $(PROTOC_GEN_GO)
	$(PROTOC) --plugin=$(PROTOC_GEN_GO) --go_opt=Mjava/errorlimitserver/src/main/proto/helloworld.proto=./helloworld --go_out=plugins=grpc:. $<

python/helloworld_pb2.py: java/errorlimitserver/src/main/proto/helloworld.proto $(BUILD_DIR)/venv
	# TODO: Use the main venv with grpcio-tools updates to the latest protobuf
	$(BUILD_DIR)/venv/bin/python3 -m venv $(BUILD_DIR)/venv_protoc
	$(BUILD_DIR)/venv_protoc/bin/pip install grpcio-tools==1.47.0
	$(BUILD_DIR)/venv_protoc/bin/python3 -m grpc_tools.protoc --proto_path=java/errorlimitserver/src/main/proto --python_out=python --grpc_python_out=python $<

# download protoc to a temporary tools directory
$(PROTOC): buildtools/getprotoc.go | $(BUILD_DIR)
	go run $< --outputDir=$(BUILD_DIR)

# I think the version of protoc-gen-go is specified by the version of protobuf in go.mod
$(PROTOC_GEN_GO): go.mod | $(BUILD_DIR)
	go build -o $@ github.com/golang/protobuf/protoc-gen-go

$(BUILD_DIR):
	mkdir -p $@

clean:
	$(RM) -r $(BUILD_DIR) python/__pycache__ helloworld/*.pb.go python/*_pb2*.py

docker:
	docker build . --tag=gcr.io/networkping/grpclimitsserver:$(shell date '+%Y%m%d')-$(shell git rev-parse --short=10 HEAD)
	docker run --rm -ti gcr.io/networkping/grpclimitsserver:$(shell date '+%Y%m%d')-$(shell git rev-parse --short=10 HEAD) --help
	docker build -f Dockerfile.pythonclient . --tag=gcr.io/networkping/pythonclient:$(shell date '+%Y%m%d')-$(shell git rev-parse --short=10 HEAD)
	docker run --rm -ti gcr.io/networkping/pythonclient:$(shell date '+%Y%m%d')-$(shell git rev-parse --short=10 HEAD) --help
