.PHONY: run lint test

run:
\tpython -m irun

lint:
\truff check .

test:
\tpytest -q

