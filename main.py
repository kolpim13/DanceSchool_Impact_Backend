import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from app.core.config import settings

# Routers
from app.modules.people.router import router as people_router
#=====================================================

def create_app() -> FastAPI:
    application = FastAPI(title=settings.title, version='0.2.0')
    application.include_router(people_router, prefix='/api')

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
