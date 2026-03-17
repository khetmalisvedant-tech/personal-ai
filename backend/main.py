from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import router as app_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(app_router)

@app.get("/")
def home():
    return {"message": "AI Voice Tutor Running 🚀"}