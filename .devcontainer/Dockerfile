FROM python:3.14-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

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

ENV SEPLIS_PLAY__FFMPEG_FOLDER="/usr/lib/jellyfin-ffmpeg"

WORKDIR /app
