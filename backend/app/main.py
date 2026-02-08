from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import conversation_routes, learning_routes

app = FastAPI(title="SupportMind Backend")

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversation_routes.router, prefix="/api")
app.include_router(learning_routes.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Service is running"}
