from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from engine import Engine

app = FastAPI()

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    prompt: str
    model: str = "llama3"
    temperature: float = 0.7
    mode:str="normal"

@app.post("/chat")
async def chat(request: ChatRequest):
    system_prompt = ""

    if request.mode == "short":
        system_prompt = "Give very short and concise answers."
    elif request.mode == "teacher":
        system_prompt = "Explain clearly step by step like a teacher."
    elif request.mode == "coder":
        system_prompt = "Give precise technical answers with code when needed."
    elif request.mode == "friend":
        system_prompt = "Respond in a friendly and casual manner."

    full_prompt = f"{system_prompt}\n\n{request.prompt}"

    engine = Engine(
        model=request.model,
        temperature=request.temperature
    )

    async def stream():
        async for chunk in engine.generate(full_prompt):
            yield chunk

    return StreamingResponse(stream(), media_type="text/plain")


@app.get("/")
def root():
    return {"status": "Backend running"}