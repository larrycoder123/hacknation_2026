from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import endpoints, learning_endpoints

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

app.include_router(endpoints.router, prefix="/api")
app.include_router(learning_endpoints.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Service is running"}
