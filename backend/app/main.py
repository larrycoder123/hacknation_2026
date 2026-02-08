"""FastAPI application entry point.

Configures CORS middleware and registers the conversation and learning
API routers under the /api prefix. Health check at GET /.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import conversation_routes, learning_routes
from .core.config import get_settings

app = FastAPI(title="SupportMind Backend")

settings = get_settings()
origins = [o.strip() for o in settings.cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(conversation_routes.router, prefix="/api")
app.include_router(learning_routes.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Service is running"}
