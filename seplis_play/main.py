from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from seplis_play.config import config

from .database import database
from .routes import (
    close_session_routes,
    download_source_routes,
    health_routes,
    hls_routes,
    keep_alive_routes,
    request_media_routes,
    sources_routes,
    subtitle_file_routes,
    thumbnails_routes,
    transcode_decision_routes,
)
from .transcoding.base_transcoder import close_session, sessions


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    database.setup()
    yield

    await database.engine.dispose()

    for session in list(sessions):
        await close_session(session)


app = FastAPI(title='SEPLIS Play Server', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(health_routes.router)
app.include_router(sources_routes.router)
app.include_router(thumbnails_routes.router)
app.include_router(keep_alive_routes.router)
app.include_router(subtitle_file_routes.router)
app.include_router(close_session_routes.router)
app.include_router(download_source_routes.router)
app.include_router(request_media_routes.router)
app.include_router(transcode_decision_routes.router)
app.include_router(hls_routes.router)

# The media.m3u8 gets updated too fast and the browser gets an old version
StaticFiles.is_not_modified = lambda *args, **kwargs: False
app.mount('/files', StaticFiles(directory=config.transcode_folder), name='files')
