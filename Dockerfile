# CLAUDE.md §4: latest を使わずタグで Python を固定する
FROM python:3.13.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# uv バイナリを公式イメージからコピー（バージョン固定）
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /usr/local/bin/

WORKDIR /app

# 依存を先に焼く（CLAUDE.md §4: uv sync --frozen で uv.lock に厳密一致）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# プロジェクトソース
COPY src ./src
COPY tests ./tests
COPY experiments ./experiments
COPY README.md ./
RUN uv sync --frozen --no-dev

CMD ["python", "-m", "tsumiki.smoke.japanese_check"]
