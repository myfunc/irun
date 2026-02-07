.PHONY: run lint test mvp-run mvp-lint mvp-test

run:
	$(MAKE) mvp-run

lint:
	$(MAKE) mvp-lint

test:
	$(MAKE) mvp-test

mvp-run:
	cd apps/mvp && python -m mvp

mvp-lint:
	cd apps/mvp && ruff check .

mvp-test:
	cd apps/mvp && pytest -q
