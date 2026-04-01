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

ENV JEMALLOC_VERSION=5.3.0

RUN apt-get update && \
    apt-get install -yq wget pwgen gcc make bzip2 && \
    rm -rf /var/lib/apt/lists/* && \
    wget -q https://github.com/jemalloc/jemalloc/releases/download/$JEMALLOC_VERSION/jemalloc-$JEMALLOC_VERSION.tar.bz2 && \
    tar jxf jemalloc-*.tar.bz2 && \
    rm jemalloc-*.tar.bz2 && \
    cd jemalloc-* && \
    ./configure --enable-prof --enable-stats --enable-debug --enable-fill && \
    make && \
    make install && \
    cd - && \
    rm -rf jemalloc-* && \
    apt-get remove -yq wget pwgen gcc make bzip2 && \
    rm -rf /usr/share/doc /usr/share/man && \
    apt-get clean autoclean && \
    apt-get autoremove -y && \
    rm -rf /var/lib/{apt,dpkg,cache,log}/

FROM python:3.14-slim-trixie

RUN \
  apt-get update && \
  apt-get install -y --no-install-recommends curl gnupg && \
  curl -s https://repo.jellyfin.org/debian/jellyfin_team.gpg.key | gpg --dearmor | tee /usr/share/keyrings/jellyfin.gpg >/dev/null && \
  echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/jellyfin.gpg] https://repo.jellyfin.org/debian trixie main' > /etc/apt/sources.list.d/jellyfin.list && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
    mesa-va-drivers \
    jellyfin-ffmpeg7 && \
  apt-get remove -y curl gnupg && \
  apt-get autoremove -y && \
  rm -rf \
    /tmp/* \
    /var/lib/apt/lists/* \
    /var/tmp/*


ENV PYTHONPATH="." \
    UID=10000 \
    GID=10001 \
    SEPLIS_PLAY__FFMPEG_FOLDER="/usr/lib/jellyfin-ffmpeg"

COPY --from=pybuilder /usr/local/lib/libjemalloc.so /usr/local/lib/libjemalloc.so
ENV LD_PRELOAD="/usr/local/lib/libjemalloc.so"
ENV MALLOC_CONF="background_thread:true,dirty_decay_ms:5000,muzzy_decay_ms:5000,narenas:2,tcache_max:8192"

COPY --from=pybuilder --chown=app:app /app /app

RUN addgroup --gid $GID --system seplis; adduser --uid $UID --system --gid $GID seplis
USER $UID:$GID

WORKDIR /app

ENTRYPOINT ["python", "seplis_play/runner.py"]