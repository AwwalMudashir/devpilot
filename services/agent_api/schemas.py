from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    project_id: str

class ChatResponse(BaseModel):
    answer: str


