import os
from openai import OpenAI
from app.supabase import supabase

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def retrieve_relevant_rules(query: str, match_count: int = 5):
    """
    Retrieves the most relevant SRD rules from Supabase using vector similarity search.
    """
    # Create embedding for the user query
    embedding = client.embeddings.create(
        model="text-embedding-ada-002",
        input=query
    ).data[0].embedding

    # Run similarity search on Supabase
    # This assumes your table is called 'rules_embeddings'
    # and has an 'embedding' column of type vector(1536)
    response = supabase.rpc(
        "match_rules",  # This will be a SQL function we'll make in step 2
        {"query_embedding": embedding, "match_count": match_count}
    ).execute()

    return [match["content"] for match in response.data]
