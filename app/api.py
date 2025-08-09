from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime
from app.langgraph_runner import run_dm_graph
from app.supabase import supabase
from app.vectorstore.retriever import retrieve_relevant_rules

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
    return run_dm_graph(user_input=request.input, history=request.history)

# === /chat/init ===
@router.post("/chat/init")
def init_ai_context(req: InitRequest):
    try:
        # --- 1. Build base context string ---
        context_str = f"Campaign started by player '{req.player_name}'."
        print(f"Character data provided: {req.character}")
        if req.character:
            context_str += (
                f" They are playing a {req.character.get('race', 'Unknown')} "
                f"{req.character.get('class', 'Unknown')} named {req.character.get('name', 'Unknown')}."
            )

        # --- 2. Ensure character info is always a dict ---
        character_data = req.character if isinstance(req.character, dict) else {}

        # --- 3. Store context text + raw character in Supabase ---
        context_obj = {
            "campaign_id": req.campaign_id,
            "context_text": context_str,
            "character": character_data,  # <-- Persist character for later use
            "created_by": req.player_name,
        }

        result = (
            supabase.table("campaign_ai_contexts")
            .upsert(
                {
                    "campaign_id": req.campaign_id,
                    "context_json": context_obj,
                    "updated_at": datetime.utcnow().isoformat()
                },
                on_conflict="campaign_id"
            )
            .execute()
        )

        if not result or not getattr(result, "data", None):
            raise HTTPException(status_code=500, detail="Upsert failed. No data returned from Supabase.")

        # --- 4. Fetch existing chat history ---
        messages_result = (
            supabase.table("campaign_ai_messages")
            .select("*")
            .eq("campaign_id", req.campaign_id)
            .order("created_at", desc=False)
            .execute()
        )

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in getattr(messages_result, "data", [])
        ]

        # --- 5. Return success + full context + chat history ---
        return {"success": True, "context": context_obj, "history": history}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize context: {str(e)}")




# === /chat ===

@router.post("/chat")
def chat(request: ChatRequest):
    """
    Main chat endpoint for interacting with the AI DM.
    Loads campaign/player context from Supabase,
    retrieves relevant D&D rules, merges both,
    sends to AI, saves conversation.
    """

    # === 1. Load campaign context ===
    context_data = {}
    try:
        response = (
            supabase
            .from_("campaign_ai_contexts")
            .select("context_json")
            .eq("campaign_id", request.campaign_id)
            .single()
            .execute()
        )

        if hasattr(response, "data") and response.data and "context_json" in response.data:
            context_data = response.data["context_json"]
        else:
            print(f"No context found for campaign_id={request.campaign_id}")

    except Exception as e:
        print("Failed to fetch context:", e)

    # === 2. Merge character info into readable context ===
    # Merge character details into context
    merged_context = context_data or {}
    char = merged_context.get("character")
    if char:
        char_str = (
            f"\n\nCharacter Details:\n"
            f"- Name: {char.get('name', 'Unknown')}\n"
            f"- Race: {char.get('race', 'Unknown')}\n"
            f"- Class: {char.get('class', 'Unknown')}\n"
            f"- Background: {char.get('background', 'Unknown')}"
        )
        merged_context["context_text"] = merged_context.get("context_text", "") + char_str


    # === 3. Retrieve relevant rules from SRD ===
    try:
        relevant_rules = retrieve_relevant_rules(request.message, match_count=5)
        rules_context = "\n".join(relevant_rules) if relevant_rules else ""
    except Exception as e:
        print("Failed to retrieve relevant rules:", e)
        rules_context = ""

    # === 4. Convert history list into a formatted string ===
    history_string = "\n".join(
        f"{msg.role.capitalize()}: {msg.content}" for msg in request.history
    )

    # === 5. Run AI DM logic ===
    result = run_dm_graph(
        user_input=request.message,
        history=history_string,
        context={
            **(merged_context or {}),
            "rules_reference": rules_context
        }
    )

    # === 6. Save messages to Supabase ===
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

