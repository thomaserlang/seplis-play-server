FROM python:3.11-bullseye as pybuilder
COPY . .
ENV \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN pip wheel -r requirements.txt --wheel-dir=/wheels

FROM python:3.11-slim-bullseye
RUN apt-get update; apt-get upgrade -y; apt-get install curl fontconfig -y
ENV \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH="${PYTHONPATH}:." \
    UID=10000 \
    GID=10001

COPY . .

COPY --from=pybuilder /wheels /wheels
RUN pip install --no-index --find-links=/wheels -r requirements.txt

COPY --from=mwader/static-ffmpeg:6.0 /ffmpeg /usr/local/bin/
COPY --from=mwader/static-ffmpeg:6.0 /ffprobe /usr/local/bin/

RUN addgroup --gid $GID --system seplis; adduser --uid $UID --system --gid $GID seplis
USER $UID:$GID
ENTRYPOINT ["python", "seplis_play_server/runner.py"]

# docker build -t seplis/seplis-play-server --rm . 
# docker push seplis/seplis-play-server:latest 