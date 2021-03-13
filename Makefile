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

$(BUILD_DIR)/.pythoncheck: python/pythonclient.py python/pythonserver.py | $(BUILD_DIR)/venv
	$(BUILD_DIR)/venv/bin/black python
	PYTHONPATH=python $(BUILD_DIR)/venv/bin/mypy --follow-imports=silent --strict --allow-untyped-calls $^
	touch $@

$(BUILD_DIR):
	mkdir -p $@

clean:
	$(RM) -r $(BUILD_DIR) python/__pycache__
