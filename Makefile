PYTHON = python3
POETRY ?= poetry

ifeq ($(OS), Darwin)
	OPEN := open
else
	OPEN := xdg-open
endif

.PHONY: init
init:
	$(POETRY) install

.PHONY: update
update:
	$(POETRY) lock
	$(POETRY) install

.PHONY: yapf
yapf:
	$(POETRY) run yapf -r --diff .

.PHONY: flake8
flake8:
	$(POETRY) run flake8 . \
		--select=E9,F63,F7,F82 \
		--show-source \
		--statistics
	# Full linter run.
	$(POETRY) run flake8 --max-line-length=96 --exclude storage .

.PHONY: format
format:
	make flake8; make yapf

.PHONY: do-yapf
do-yapf:
	$(POETRY) run yapf -i -r .

.PHONY: test
test:
	$(POETRY) run pytest

.PHONY: coverage
coverage:
	$(POETRY) run pytest --cov-report html:coverage \
		--cov=src \
		tests/
	$(OPEN) coverage/index.html