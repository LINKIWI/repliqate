ARCHITECTURE ?= "unknown"
VERSION ?= "unknown"

bootstrap:
	pip install -r requirements.txt

lint:
	flake8 repliqate

build:
	$(eval BUILD_WORKDIR := $(shell mktemp -d))
	mkdir -p dist/
	echo -n $(VERSION) > VERSION
	pyinstaller \
		--name repliqate \
		--distpath $(BUILD_WORKDIR) \
		--add-data "VERSION:repliqate/meta" \
		--clean \
		--onefile \
		repliqate/cmd/main.py
	staticx \
		--loglevel INFO \
		--no-compress \
		$(BUILD_WORKDIR)/repliqate \
		dist/repliqate-$(ARCHITECTURE)
	chmod +rx dist/repliqate-$(ARCHITECTURE)

.PHONY: bootstrap lint build
