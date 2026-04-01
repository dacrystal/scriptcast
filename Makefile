.PHONY: lint typecheck test all

lint:
	ruff check .

typecheck:
	mypy scriptcast/

test:
	pytest --cov=scriptcast --cov-report=term-missing

all: lint typecheck test
