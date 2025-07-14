from fastapi import APIRouter
from pydantic import BaseModel
from app.langgraph_runner import run_dm_graph

router = APIRouter()

class DMRequest(BaseModel):
    input: str
    history: str = ""

@router.post("/respond")
def get_dm_response(request: DMRequest):
    result = run_dm_graph(user_input=request.input, history=request.history)
    return result
