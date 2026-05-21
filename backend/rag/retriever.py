"""
rag/retriever.py — MultiQueryRetriever wrapped as a LangChain tool.

MultiQueryRetriever generates 3 query variants per user question,
runs all 3 against ChromaDB, and deduplicates results — giving better
recall than a single similarity search.
"""

from typing import List

from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.tools import tool
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from config import settings


def get_rag_tool(vectorstore, base_k: int = 4):
    """
    Factory: returns a LangChain @tool bound to the given vectorstore.
    Call once at agent creation time — pass to create_nutribot_agent().
    """
    base_retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": base_k},
    )
    mqr = MultiQueryRetriever.from_llm(
        retriever=base_retriever,
        llm=ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.openai_api_key,
        ),
    )

    @tool
    def search_nutrition_knowledge(query: str) -> str:
        """
        Search the NutriBot nutrition knowledge base for evidence-based information.
        Use this tool for ANY question about:
        - Healthy eating, macros, micros, food groups, hydration
        - Weight loss strategies, TDEE, BMR, caloric deficit
        - Vegan and vegetarian nutrition (B12, iron, omega-3, protein sources)
        - Halal food rules, hidden haram ingredients, halal certification
        - Food allergies, intolerances, cross-contamination (14 EU allergens)
        - Meal planning, batch cooking, portion sizes, eating out tips
        Always call this before answering nutrition knowledge questions.
        """
        docs: List[Document] = mqr.invoke(query)
        if not docs:
            return "No relevant information found in the knowledge base."

        results = []
        for doc in docs[:6]:
            source = doc.metadata.get("source", "unknown")
            source_name = (
                source.split("/")[-1]
                .replace(".md", "")
                .replace("_", " ")
                .title()
            )
            results.append(f"[Source: {source_name}]\n{doc.page_content.strip()}")

        return "\n\n---\n\n".join(results)

    return search_nutrition_knowledge
