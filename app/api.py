from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from app.langgraph_runner import run_dm_graph
from app.supabase import supabase

router = APIRouter()

# === Request Models ===

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[Message]
    campaign_id: str
    player_name: str

class InitRequest(BaseModel):
    campaign_id: str
    player_name: str
    character: dict | None = None  # Optional character data

class DMRequest(BaseModel):
    input: str
    history: str = ""

# === /respond (raw DM runner) ===

@router.post("/respond")
def get_dm_response(request: DMRequest):
    result = run_dm_graph(user_input=request.input, history=request.history)
    return result

# === /chat/init ===

@router.post("/chat/init")
def init_ai_context(req: InitRequest):
    try:
        context_str = f"Campaign started by player '{req.player_name}'."
        if req.character:
            context_str += (
                f" They are playing a {req.character.get('race')} "
                f"{req.character.get('class')} named {req.character.get('name')}."
            )

        context_obj = {
            "campaign_id": req.campaign_id,
            "context_text": context_str,
            "created_by": req.player_name,
        }

        result = supabase.table("campaign_ai_contexts") \
            .upsert({
                "campaign_id": req.campaign_id,
                "context_json": context_obj,
                "updated_at": datetime.utcnow().isoformat()
            }, on_conflict="campaign_id") \
            .execute()

        print("Supabase upsert result:", result)

        if not result or not result.data:
            raise HTTPException(status_code=500, detail="Upsert failed. No data returned from Supabase.")

        # Also fetch existing messages to restore frontend state
        messages_result = supabase \
            .table("campaign_ai_messages") \
            .select("*") \
            .eq("campaign_id", req.campaign_id) \
            .order("created_at", desc=False) \
            .execute()

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in messages_result.data
        ]

        return {"success": True, "context": context_obj, "history": history}

    except Exception as e:
        print("Error in /chat/init:", e)
        raise HTTPException(status_code=500, detail=f"Failed to initialize context: {str(e)}")

# === /chat ===

@router.post("/chat")
def chat(request: ChatRequest):
    context_data = {}

    try:
        response = supabase \
            .from_("campaign_ai_contexts") \
            .select("context_json") \
            .eq("campaign_id", request.campaign_id) \
            .single()

        if response.data and "context_json" in response.data:
            context_data = response.data["context_json"]
        else:
            print(f"No context found for campaign_id={request.campaign_id}")

    except Exception as e:
        print("Failed to fetch context:", e)

    result = run_dm_graph(
        user_input=request.message,
        history=request.history,
        context=context_data or {}
    )

    try:
        supabase.table("campaign_ai_messages").insert({
            "campaign_id": request.campaign_id,
            "role": "user",
            "content": request.message,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        supabase.table("campaign_ai_messages").insert({
            "campaign_id": request.campaign_id,
            "role": "ai",
            "content": result["response"],
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print("Failed to save messages to Supabase:", e)

    return result

