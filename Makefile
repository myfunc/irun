.PHONY: run lint test mvp-run mvp-lint mvp-test ivan-run ivan-lint ivan-test

run:
	$(MAKE) ivan-run

lint:
	$(MAKE) mvp-lint
	$(MAKE) ivan-lint

test:
	$(MAKE) mvp-test
	$(MAKE) ivan-test

mvp-run:
	cd apps/mvp && python -m mvp

mvp-lint:
	cd apps/mvp && ruff check .

mvp-test:
	cd apps/mvp && pytest -q

ivan-run:
	cd apps/ivan && python -m ivan

ivan-lint:
	cd apps/ivan && ruff check .

ivan-test:
	cd apps/ivan && pytest -q
