import asyncio
import os
import sqlite3
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from app.core.config import settings

# Routers
from app.modules.people.router import router as people_router
from app.modules.people.service import PHOTO_DIRECTORY

from app.modules.social_media.router import router as social_media_router
from app.modules.social_media.sync import refresh_facebook_feed
#=====================================================

@asynccontextmanager
async def lifespan(application: FastAPI):
    # Run in a worker thread so a slow Facebook call never delays startup.
    if os.environ.get('IMPACT_DISABLE_STARTUP_SYNC') != '1':
        asyncio.get_running_loop().run_in_executor(None, refresh_facebook_feed)
    yield


def create_app() -> FastAPI:
    application = FastAPI(title=settings.title, version='0.2.0', lifespan=lifespan)
    PHOTO_DIRECTORY.mkdir(parents=True, exist_ok=True)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.website_origins),
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    application.mount('/media', StaticFiles(directory=PHOTO_DIRECTORY.parent), name='media')
    application.include_router(people_router, prefix='/api')
    application.include_router(social_media_router, prefix='/api')

    @application.exception_handler(OperationalError)
    async def database_error(request: Request, exc: OperationalError):
        code = getattr(exc.orig, 'sqlite_errorcode', None)
        if code is not None and (code & 0xff) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            return JSONResponse(status_code=503, content={'detail': 'Database busy; retry the request'}, headers={'Retry-After': '1'})
        return JSONResponse(status_code=500, content={'detail': 'Database operation failed'})

    return application
#=====================================================


app = create_app()
#=====================================================
