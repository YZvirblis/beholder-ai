import os
from dotenv import load_dotenv
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from pathlib import Path

load_dotenv()

with open(Path("app/prompts/dm_prompt.txt"), "r", encoding="utf-8") as f:
    prompt_template_str = f.read()

prompt_template = PromptTemplate.from_template(prompt_template_str)

llm = ChatOpenAI(model="gpt-4", temperature=0.7)

def run_dm_graph(user_input: str, history: str = ""):
    prompt = prompt_template.format(history=history, input=user_input)
    response = llm.invoke(prompt)
    
    updated_history = f"{history}\nPlayer: {user_input}\nDM: {response.content}"

    return {
        "response": response.content,
        "history": updated_history,
    }
