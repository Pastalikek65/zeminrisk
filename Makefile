.PHONY: all test rust-test py-test build up down sim clean fmt frontend-install frontend-dev frontend-build

all: test build

fmt:
	cargo fmt --all
	uv run ruff format .
	uv run ruff check --fix .

rust-test:
	cargo test --workspace

py-test:
	uv run pytest

test: rust-test py-test

build:
	cargo build --release

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

up:
	docker compose up -d

down:
	docker compose down

sim:
	cargo run -p zemin-rt

serve:
	uv run python -m zemin.cli serve --port 8000 --reload

clean:
	cargo clean
	rm -rf .venv data_sample.geojson
