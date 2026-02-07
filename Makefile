.PHONY: run lint test up-run up-lint up-test

run:
	$(MAKE) up-run

lint:
	$(MAKE) up-lint

test:
	$(MAKE) up-test

up-run:
	cd apps/up && python -m up

up-lint:
	cd apps/up && ruff check .

up-test:
	cd apps/up && pytest -q
