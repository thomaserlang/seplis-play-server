from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from seplis_play_server.config import config
from seplis_play_server.logger import set_logger

set_logger(f'play-server-{config.port}.log')

from .database import database
from .routes import (
    close_session,
    download_source,
    health,
    hls,
    keep_alive,
    request_media,
    sources,
    subtitle_file,
    thumbnails,
)

app = FastAPI(
    title='SEPLIS Play Server'
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(health.router)
app.include_router(sources.router)
app.include_router(thumbnails.router)
app.include_router(keep_alive.router)
app.include_router(subtitle_file.router)
app.include_router(close_session.router)
app.include_router(download_source.router)
app.include_router(request_media.router)
app.include_router(hls.router)

# The media.m3u8 gets updated too fast and the browser gets an old version
StaticFiles.is_not_modified = lambda *args, **kwargs: False
app.mount('/files', StaticFiles(directory=config.transcode_folder), name='files')

@app.on_event('startup')
async def startup():
    database.setup()

@app.on_event('shutdown')
async def shutdown():
    await database.engine.dispose()

    from .transcoders.video import close_session as cs
    from .transcoders.video import sessions
    for session in list(sessions):
        cs(session)