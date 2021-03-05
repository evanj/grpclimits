all: .gocheck_stamp python/venv

.gocheck_stamp: $(wildcard **/*.go)
	go test ./...
	go vet ./...
	golint ./...
	staticcheck ./...
	go mod tidy
	touch .gocheck_stamp


python/venv: python/requirements.txt python/requirements_build.txt
	rm -rf python/venv
	python3 -m venv python/venv
	python/venv/bin/pip install -r python/requirements_build.txt
	python/venv/bin/pip install -r python/requirements.txt
