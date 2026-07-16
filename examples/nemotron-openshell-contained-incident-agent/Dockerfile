# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.11.24 AS uv

FROM python:3.12-slim-trixie AS builder

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app

# Socket Firewall protects the dependency install performed during the image build.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && machine="$(uname -m)" \
    && case "$machine" in \
         x86_64) \
           sfw_arch="x86_64"; \
           sfw_sha="4dc46b626a7c5b81c0b54e1984ee53be5a628dbfb2f55ab14e9b04c8a134db6a" ;; \
         aarch64|arm64) \
           sfw_arch="arm64"; \
           sfw_sha="f87bbbca2192fca9740f9bdb115e7cfaa22e957a8f5234d5f97fce1383aa1d66" ;; \
         *) echo "Unsupported architecture for sfw: $machine" >&2; exit 1 ;; \
       esac \
    && curl --fail --silent --show-error --location \
       "https://github.com/SocketDev/sfw-free/releases/download/v1.13.1/sfw-free-linux-${sfw_arch}" \
       --output /usr/local/bin/sfw \
    && echo "${sfw_sha}  /usr/local/bin/sfw" | sha256sum --check --status \
    && chmod 0755 /usr/local/bin/sfw

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN sfw uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-trixie AS runtime

RUN apt-get update \
    && apt-get install --yes --no-install-recommends iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 sandbox \
    && useradd --uid 1000 --gid sandbox --create-home sandbox \
    && mkdir -p /app /sandbox \
    && chown sandbox:sandbox /sandbox

COPY --from=builder /app /app
COPY skills /app/skills
COPY workshop /app/workshop

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODEL_PROVIDER=nvidia \
    NVIDIA_MODEL=nvidia/nemotron-3-ultra-550b-a55b \
    OPENSHELL_EXECUTION_BOUNDARY=openshell-contained

USER sandbox
WORKDIR /app

CMD ["sleep", "infinity"]
