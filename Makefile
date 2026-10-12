.PHONY: install fmt lint types layers file-length todos test coverage-thresholds check clean \
	lambda-build lambda-deploy lambda-teardown

install:
	uv sync --all-extras --all-groups

fmt:
	uv run ruff format --check .

lint:
	uv run ruff check .

types:
	uv run mypy --strict src scripts infra/aws

layers:
	uv run lint-imports

file-length:
	uv run python scripts/check_file_length.py

todos:
	uv run python scripts/check_todos.py

test:
	uv run pytest -q

coverage-thresholds:
	uv run coverage report --include="*/costwise/domain/*" --fail-under=95
	uv run coverage report --include="*/costwise/services/*" --fail-under=90

check: fmt lint types layers file-length todos test coverage-thresholds

clean:
	uv run python scripts/clean_workspace.py

lambda-build:
	uv run python infra/aws/deploy.py build

lambda-deploy:
	uv run python infra/aws/deploy.py deploy

lambda-teardown:
	uv run python infra/aws/teardown.py
