.PHONY: run lint test ivan-run ivan-lint ivan-test

run:
	$(MAKE) ivan-run

lint:
	$(MAKE) ivan-lint

test:
	$(MAKE) ivan-test

ivan-run:
	cd apps/ivan && ( [ -x .venv/bin/python ] && .venv/bin/python -m ivan || python3 -m ivan )

ivan-lint:
	cd apps/ivan && ( [ -x .venv/bin/ruff ] && .venv/bin/ruff check . || ruff check . )

ivan-test:
	cd apps/ivan && ( [ -x .venv/bin/pytest ] && .venv/bin/pytest -q || pytest -q )
