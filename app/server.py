import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))
from chat import ask

app = FastAPI()

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        reply = ask(req.message, req.history if req.history else None)
        return {"reply": reply}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
