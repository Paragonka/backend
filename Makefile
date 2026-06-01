.PHONY: lint lint-check test audit clean check

lint:
	uv run ruff check . --fix
	uv run ruff format .
	uv run pyright

lint-check:
	@status=0; \
	uv run ruff check . || status=$$?; \
	uv run ruff format . --check || status=$$?; \
	uv run pyright || status=$$?; \
	exit $$status

test:
	uv run pytest --cov=app --cov-report=term-missing

audit:
	uv audit

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Cleanup complete: __pycache__ and .pyc files removed."

check:
	$(MAKE) lint
	$(MAKE) test
	$(MAKE) audit
