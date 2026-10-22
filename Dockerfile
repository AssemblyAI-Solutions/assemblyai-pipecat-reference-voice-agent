# syntax=docker/dockerfile:1
# Pipecat Cloud's base image runs bot() from /app/bot.py.
# Adapted from https://github.com/pipecat-ai/pipecat-quickstart
FROM dailyco/pipecat-base:latest

# Compile bytecode at install time for a faster cold start, and copy rather than link from the
# cache, which is a mounted volume
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Dependencies first, so code-only changes reuse this layer. Run `uv sync` once locally to
# create uv.lock, and commit it.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY ./src/ ./
