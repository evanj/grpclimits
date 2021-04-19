BUILD_DIR:=build

all: $(BUILD_DIR)/.gocheck_stamp $(BUILD_DIR)/venv $(BUILD_DIR)/.pythoncheck

$(BUILD_DIR)/.gocheck_stamp: $(wildcard **/*.go) | $(BUILD_DIR)
	go test ./...
	go vet ./...
	golint ./...
	staticcheck ./...
	go mod tidy
	touch $@

$(BUILD_DIR)/venv: python/requirements.txt python/requirements_build.txt
	rm -rf $@
	python3 -m venv $@
	$@/bin/pip install -r python/requirements_build.txt
	$@/bin/pip install -r python/requirements.txt

# recursive wildcard function from
# https://blog.jgc.org/2011/07/gnu-make-recursive-wildcard-function.html
rwildcard=$(foreach d,$(wildcard $1*),$(call rwildcard,$d/,$2) $(filter $(subst *,%,$2),$d))

PYTHON_FILES:=$(filter-out python/helloworld_pb2%.py, $(call rwildcard,python,*.py))
$(BUILD_DIR)/.pythoncheck: $(PYTHON_FILES) | $(BUILD_DIR)/venv
	echo $^
	echo $(PYTHON_FILES)
	$(BUILD_DIR)/venv/bin/black --line-length=100 python
	PYTHONPATH=python $(BUILD_DIR)/venv/bin/mypy --follow-imports=silent --strict --allow-untyped-calls $^
	PYTHONPATH=python $(BUILD_DIR)/venv/bin/pytest --log-level=debug
	touch $@

$(BUILD_DIR):
	mkdir -p $@

clean:
	$(RM) -r $(BUILD_DIR) python/__pycache__
