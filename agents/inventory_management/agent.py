import os
import json
from typing import TypedDict, List, Dict, Any
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq

from .tools import fetch_inventory_from_api, store_inventory, get_historical_sales
from shared.models import InventoryAgentOutput

load_dotenv()

class AgentState(TypedDict):
    current_inventory: List[Dict[str, Any]]
    historical_sales: List[Dict[str, Any]]
    final_output: Any # InventoryAgentOutput

def fetch_data_node(state: AgentState):
    """Fetches inventory from API, stores it, and gets historical sales."""
    print("--- Node: Fetching Current Inventory & History ---")
    raw_inventory, compact_inventory = fetch_inventory_from_api()
    
    store_inventory(raw_inventory)
    
    historical = get_historical_sales()
    
    return {
        "current_inventory": compact_inventory,
        "historical_sales": historical
    }

def analyze_demand_node(state: AgentState):
    """Passes the collected data to the LLM to get structured JSON."""
    print("--- Node: Analyzing Demand via LLM ---")
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_retries=5
    )
    
    structured_llm = llm.with_structured_output(InventoryAgentOutput)
    
    system_prompt = """
    You are an inventory planning expert.
    
    You receive today's inventory snapshot and historical records.
    Your task is to analyze demand trends, identify both top-selling products 
    and low-stock products, and output a single combined list of products 
    that require replenishment along with their recommended quantities.
    """
    
    user_prompt = f"""
    Based on the following data, generate the combined list of top-selling and low-stock products that need replenishment.
    
    Current Inventory Snapshot:
    {json.dumps(state.get("current_inventory", []))}
    
    Historical Sales (last 5 records):
    {json.dumps(state.get("historical_sales", []))}
    """
    
    messages = [
        ("system", system_prompt),
        ("human", user_prompt)
    ]
    
    print("--- Calling Groq via LangChain ---")
    result = structured_llm.invoke(messages)
    return {"final_output": result}


# Build Graph
builder = StateGraph(AgentState)
builder.add_node("fetch_data", fetch_data_node)
builder.add_node("analyze_demand", analyze_demand_node)

builder.add_edge(START, "fetch_data")
builder.add_edge("fetch_data", "analyze_demand")
builder.add_edge("analyze_demand", END)

inventory_graph = builder.compile()
