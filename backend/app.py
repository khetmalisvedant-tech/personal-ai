from fastapi import APIRouter
from pydantic import BaseModel
from core import process_query

router = APIRouter()


class QuestionRequest(BaseModel):
    question: str


@router.post("/ask")
async def ask(data: QuestionRequest):
    question = data.question.strip()

    if not question:
        return {"error": "No question provided"}

    return process_query(question)
