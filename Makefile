.PHONY: setup check fix upgrade test

setup:
	@command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
	uv sync

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest

fix:
	uv run ruff check --fix .
	uv run ruff format .

upgrade:
	uv lock --upgrade
	uv sync --upgrade

test:
	uv run pytest
