FROM ghcr.io/astral-sh/uv:python3.14-trixie AS pybuilder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

FROM python:3.14-slim-trixie

ARG JELLYFIN_FFMPEG_VERSION=8.1.2-3-trixie

RUN \
  apt-get update && \
  apt-get install -y --no-install-recommends curl gnupg && \
  curl -s https://repo.jellyfin.org/debian/jellyfin_team.gpg.key | gpg --dearmor | tee /usr/share/keyrings/jellyfin.gpg >/dev/null && \
  echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/jellyfin.gpg] https://repo.jellyfin.org/debian trixie main' > /etc/apt/sources.list.d/jellyfin.list && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
    mesa-va-drivers \
    jellyfin-ffmpeg8="${JELLYFIN_FFMPEG_VERSION}" && \
  apt-get remove -y curl gnupg && \
  apt-get autoremove -y && \
  rm -rf \
    /tmp/* \
    /var/lib/apt/lists/* \
    /var/tmp/*


ENV PYTHONPATH="." \
    PATH="/app/.venv/bin:$PATH" \
    UID=10000 \
    GID=10001 \
    SEPLIS_PLAY__FFMPEG_FOLDER="/usr/lib/jellyfin-ffmpeg"

COPY --from=pybuilder --chown=app:app /app /app

RUN addgroup --gid $GID --system seplis; adduser --uid $UID --system --gid $GID seplis
USER $UID:$GID

WORKDIR /app

ENTRYPOINT ["python", "seplis_play/runner.py"]
