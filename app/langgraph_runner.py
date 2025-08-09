# app/langgraph_runner.py

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from pathlib import Path

load_dotenv()

# === Load DM Prompt Template ===
with open(Path("app/prompts/dm_prompt.txt"), "r", encoding="utf-8") as f:
    prompt_template_str = f.read()

prompt_template = PromptTemplate.from_template(prompt_template_str)

# === Initialize OpenAI Chat Model ===
llm = ChatOpenAI(model="gpt-4", temperature=0.7)

def run_dm_graph(user_input: str, history: str = "", context: dict = None):
    """
    Runs the Dungeon Master AI logic with optional extra context.
    Context can include:
    - context_text (campaign intro, player info)
    - rules_reference (retrieved SRD rules)
    - any other structured data you add later
    """
    context = context or {}

    # Core campaign/player context
    context_text = context.get("context_text", "")

    # Retrieved SRD rules or other reference material
    rules_reference = context.get("rules_reference", "")

    # Merge into one context string
    full_context = context_text
    if rules_reference:
        full_context += "\n\n📖 **Relevant D&D Rules:**\n" + rules_reference

    # Format prompt
    prompt = prompt_template.format(
        history=history,
        input=user_input,
        context=full_context.strip()
    )

        # 🔍 DEBUG LOG — See exactly what’s being sent to OpenAI
    print("\n==================== DM PROMPT SENT TO OPENAI ====================")
    print(prompt)
    print("=====================================================================\n")

    # Call the LLM
    response = llm.invoke(prompt)

    # Append this interaction to conversation history
    updated_history = f"{history}\nPlayer: {user_input}\nDM: {response.content}"

    return {
        "response": response.content,
        "history": updated_history,
    }
