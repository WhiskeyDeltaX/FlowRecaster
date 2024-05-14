from fastapi import FastAPI, Request, status, WebSocket
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware
import models
import logging
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from routers import workspaces, sockets, streamservers, users

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
	exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
	logging.error(f"{request}: {exc_str}")
	content = {'status_code': 10422, 'message': exc_str, 'data': None}
	return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(streamservers.router, prefix="/api/v1", tags=["streamservers"])
app.include_router(workspaces.router, prefix="/api/v1", tags=["workspaces"])
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(sockets.router, tags=["sockets"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, debug=True, log_level='debug', access_log=True)
