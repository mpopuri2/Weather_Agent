from llms import ask_llm_with_no_tool
from log import log_info
import json

PLANNER_PROMPT = """
You are a planning assistant. Break the user's request into a numbered
list of simple, sequential steps. Each step should require at most ONE tool.

Available tools: get_weather, calculator, save_file

Return ONLY valid JSON in this format:
{
  "steps": [
    {"step": 1, "description": "..."},
    {"step": 2, "description": "..."}
  ]
}
"""


def create_plan(goal : str, conversation_history = None):
    context = ""
    if conversation_history:
        context = f"\nPrior conversation context:\n{conversation_history}\n"
    
    messages = [
        {"role" : "system", "content" : PLANNER_PROMPT + context},
        {"role" : "user", "content" : goal}
    ]

    response = ask_llm_with_no_tool(messages)
    plan = json.loads(response.content)
    log_info(f"STEPS CREATED FOR USER PROMPT: {plan}")
    return plan["steps"]


