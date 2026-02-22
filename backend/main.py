from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.routers import photos, events, auth, chat, upload

app = FastAPI(title="PicTrace API", description="Backend for PicTrace Photo Diary")

# CORS Configuration
origins = [
    "http://localhost:5173",  # Vite Frontend
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(photos.router, prefix="/api/photos", tags=["photos"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(upload.router, prefix="/api/photos", tags=["upload"])

# Mount Static Files (for serving uploaded images)
# Assumes photos are stored in 'data/photos' or similar. 
# You might need to adjust this path based on where actual photos are.
# For now, let's assume they are somewhere accessible.
# If photos are scattered, we might need a specific endpoint to serve them by path.
# But serving from root for now if needed, or better, use a specific directory.
# Let's check where photos are typically stored. 
# Based on previous context, they might be in user directories.
# We will serve specific directories if we know them, otherwise we might rely on 
# the /api/photos/{id}/image endpoint to serve files securely.

@app.get("/")
def read_root():
    return {"message": "PicTrace API is running"}
