FROM python:3.14-slim-trixie

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG USERNAME=seplis
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/home/${USERNAME}/.local/bin:/app/.venv/bin:${PATH}" \
    SEPLIS_PLAY__FFMPEG_FOLDER="/usr/lib/jellyfin-ffmpeg"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash-completion \
        build-essential \
        ca-certificates \
        curl \
        git \
        gnupg \
        less \
        pkg-config \
        procps \
        sudo \
    && curl -fsSL https://repo.jellyfin.org/debian/jellyfin_team.gpg.key \
        | gpg --dearmor -o /usr/share/keyrings/jellyfin.gpg \
    && echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/jellyfin.gpg] https://repo.jellyfin.org/debian trixie main' \
        > /etc/apt/sources.list.d/jellyfin.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        jellyfin-ffmpeg7 \
        mesa-va-drivers \
    && groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" -m -s /bin/bash "${USERNAME}" \
    && usermod -aG sudo,video "${USERNAME}" \
    && echo "${USERNAME} ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/${USERNAME}" \
    && chmod 0440 "/etc/sudoers.d/${USERNAME}" \
    && mkdir -p /app \
    && chown "${USER_UID}:${USER_GID}" /app \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

USER ${USERNAME}
