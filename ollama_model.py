"""
ollama_model.py

Local-model version of the WeatherAgent (mirrors agent.py + llms.py's tool-calling
loop, and planner.py's step decomposition) but runs entirely against a local
Ollama model instead of the OpenAI API - no API key, no internet dependency,
no API cost.

Requires a local Ollama install with the model pulled, e.g.:
    ollama pull llama3.2

Reuses the same TOOLS registry and risky-tool approval flow as the rest of
the project (tool_register.py) so behavior matches the OpenAI-based agent -
including the human-in-the-loop confirmation before save_file runs. Also
reuses memory.py's save_memory()/load_memory() for persistent conversation
history across runs, same as main.py - written to its own file (see
MEMORY_FILE below) rather than memory/session.json, since Ollama's message
shape (no tool_call_id) differs slightly from the OpenAI SDK's.

Matches V6's production-hardening checklist: persistent memory, guardrails,
human-in-the-loop approval, structured logging (via log.py, tagged
"[OLLAMA]" in agent.log so it's distinguishable from the OpenAI runs), and
per-step checkpointing (memory/ollama_checkpoint_N.json, separate from the
OpenAI version's memory/checkpoint_N.json).

NOTE: planner.py is NOT imported here on purpose - it calls the OpenAI API
under the hood (via llms.ask_llm_with_no_tool), which would silently break
the "fully offline" point of this script. Planning is reimplemented locally
below using the same Ollama model instead.
"""

import json
import re

from ollama import chat

from tool_register import TOOLS, confirm_tool_with_user, execute_tool_safely
from memory import save_memory, load_memory
from log import log_info

MODEL_NAME = "qwen2.5:7b"        # swap to "llama3.2" to try the smaller/faster local model
MEMORY_FILE = "memory/ollama_session.json"

SYSTEM_PROMPT = (
    "You are a helpful weather assistant. Only call save_file once the data it "
    "needs (e.g. weather lookups) already appears earlier in the conversation - "
    "never write placeholder, guessed, or incomplete values to a file."
)

PLANNER_SYSTEM_PROMPT = """
You are a planning assistant. Break the user's request into a numbered
list of simple, sequential steps. Each step should require at most ONE tool
call. Steps that need data produced by another tool (like calculator or
save_file) must come AFTER the step(s) that gather that data - never bundle
data-gathering and data-using steps together.

Available tools: get_weather, calculator, save_file

Return ONLY valid JSON in this format:
{
  "steps": [
    {"step": 1, "description": "..."},
    {"step": 2, "description": "..."}
  ]
}
"""

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Function is useful for retrieving the weather of a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "name of the city"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Evaluates a SINGLE Python math expression and returns one numeric result. "
                "Must be one valid expression - do NOT use semicolons or multiple statements, "
                "and do NOT call other tools/functions inside the expression. "
                "Example: 'max(69, 64, 83) - min(69, 64, 83)' to get a difference in one call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "mathematical expression to evaluate example: (2+(3*4))"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_file",
            "description": "Function is useful for saving content to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "text to save to the file"
                    }
                },
                "required": ["text"]
            }
        }
    }
]


TOOL_KEYWORDS = {
    "get_weather": ["weather", "temperature for", "current temperature"],
    "calculator": ["compar", "calculat", "differen", "math"],
    "save_file": ["save", "report", "file"],
}


def select_tools_for_step(description):
    """Restrict the tool schema offered to the model to only what a given
    plan step's description actually calls for (matched via keywords), e.g.
    a "Get current weather for Seattle" step won't even see save_file in its
    tool list. This stops the model from calling save_file (or any tool)
    early/out of turn just because it's technically available - it physically
    isn't offered unless the step is about it. Falls back to offering every
    tool if no keyword matches, so an oddly-worded step never gets stuck with
    zero usable tools."""
    description_lower = description.lower()
    selected_names = {
        tool_name
        for tool_name, keywords in TOOL_KEYWORDS.items()
        if any(keyword in description_lower for keyword in keywords)
    }

    if not selected_names:
        return TOOLS_SCHEMA

    return [t for t in TOOLS_SCHEMA if t["function"]["name"] in selected_names]


def ask_local_llm(messages, tools_schema=None):
    response = chat(model=MODEL_NAME, messages=messages, tools=tools_schema or TOOLS_SCHEMA)
    return response.message


def validate_tool_args(tool_name, args):
    """Lightweight guardrail against malformed/hallucinated tool calls, which
    local models produce far more often than gpt-4.1 does. Catches bad args
    BEFORE execution (and before any risky-tool approval prompt) so the model
    gets a corrective error fed back into the conversation instead of the
    tool either silently running on garbage input or wasting retries on an
    expression that was never going to work."""
    if tool_name not in TOOLS:
        return False, f"Unknown tool '{tool_name}'."

    if not isinstance(args, dict):
        return False, "Invalid args: expected a dict of keyword arguments."

    if tool_name == "get_weather":
        city = args.get("city", "")
        if not isinstance(city, str) or not city.strip():
            return False, "Invalid args: 'city' must be a single non-empty city name string."
        if re.search(r"[\[\]{}]", city) or (city.count(",") >= 1 and city.count("'") >= 2):
            return False, (
                f"Invalid args: 'city' looks like a list ({city!r}), not a single city name. "
                "Call get_weather once per city instead of passing multiple cities at once."
            )

    elif tool_name == "calculator":
        expression = args.get("expression", "")
        if not isinstance(expression, str) or not expression.strip():
            return False, "Invalid args: 'expression' must be a non-empty math expression."
        if re.search(r"(get_weather|save_file|calculator)\s*\(", expression):
            return False, (
                "Invalid expression: calculator cannot call other tools inside the expression. "
                "Call get_weather separately first, then pass the resulting numbers into "
                "calculator as plain numeric literals."
            )

    elif tool_name == "save_file":
        text = args.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return False, "Invalid args: 'text' must be non-empty."
        if not any(ch.isdigit() for ch in text):
            return False, (
                "Invalid args: 'text' has no actual data (no numbers found) - gather the "
                "needed results (e.g. via get_weather) before calling save_file, don't save "
                "a placeholder."
            )

    return True, None


def _parse_plan_json(content):
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
        content = content.strip()
    return json.loads(content)


def _ensure_save_step(goal, steps):
    """Plan-repair safety net: the local planner sometimes drops the save
    step entirely even when the user clearly asked to save/report something.
    If that happens, force one in code rather than silently losing it."""
    save_keywords = TOOL_KEYWORDS["save_file"]
    wants_save = any(keyword in goal.lower() for keyword in save_keywords)
    has_save_step = any(
        any(keyword in step.get("description", "").lower() for keyword in save_keywords)
        for step in steps
    )
    if wants_save and not has_save_step:
        steps = list(steps) + [{
            "step": len(steps) + 1,
            "description": "Save the final report/results to a file using save_file."
        }]
        print("Plan repair: user asked to save/report but the plan had no save step - added one.")
        log_info(f"[OLLAMA] PLAN REPAIR: appended missing save step for goal: {goal!r}")
    return steps


def create_local_plan(goal, conversation_history=None):
    """Local equivalent of planner.py's create_plan(), but calls the local
    Ollama model (no tools attached) instead of the OpenAI API."""
    context = f"\nPrior conversation context:\n{conversation_history}\n" if conversation_history else ""

    planning_messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT + context},
        {"role": "user", "content": goal}
    ]

    response = chat(model=MODEL_NAME, messages=planning_messages)  # no tools -> plain text plan

    try:
        plan = _parse_plan_json(response.message.content)
        steps = plan["steps"]
        if not steps:
            raise ValueError("planner returned no steps")
        log_info(f"[OLLAMA] STEPS CREATED FOR USER PROMPT: {steps}")
    except Exception:
        print("Local planner did not return valid JSON - falling back to a single-step plan.")
        log_info(f"[OLLAMA] PLANNER FAILED TO RETURN VALID JSON for goal: {goal!r} - using single-step fallback")
        steps = [{"step": 1, "description": goal}]

    return _ensure_save_step(goal, steps)


def run(messages, question, tools_schema=None):
    messages.append({"role": "user", "content": question})
    log_info(f"[OLLAMA] USER REQUEST: {question}")

    effective_schema = tools_schema or TOOLS_SCHEMA
    save_file_offered = any(t["function"]["name"] == "save_file" for t in effective_schema)
    save_file_called = False
    nudged = False

    response = ask_local_llm(messages, tools_schema)
    messages.append(response.model_dump())
    log_info(f"[OLLAMA] AGENT RESPONSE: {response}")

    while True:
        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.function.name
                args = tool_call.function.arguments  # ollama gives a dict directly, no json.loads needed

                if tool_name == "save_file":
                    save_file_called = True

                print(f"CALLING TOOL: {tool_name} with args {args}")
                log_info(f"[OLLAMA] TOOL CALL: {tool_name} args={args}")

                is_valid, validation_error = validate_tool_args(tool_name, args)
                if not is_valid:
                    result = f"REJECTED: {validation_error}"
                elif not confirm_tool_with_user(tool_name, args):
                    result = f"ACTION DECLINED BY USER: {tool_name} was not executed."
                else:
                    tool_function = TOOLS[tool_name]
                    result = execute_tool_safely(tool_function, args)
                print(f"  -> RESULT: {result}")
                log_info(f"[OLLAMA] TOOL RESULT: {result}")

                messages.append({
                    "role": "tool",
                    "content": str(result)
                })

            response = ask_local_llm(messages, tools_schema)
            messages.append(response.model_dump())
            log_info(f"[OLLAMA] AGENT RESPONSE: {response}")
            continue

        # Model answered in plain text with no tool call. If this step was
        # specifically offered save_file (i.e. it's meant to save something)
        # and never actually called it - local models like to *describe*
        # saving ("I will now save this...") instead of actually calling the
        # tool - nudge it once with an explicit instruction rather than
        # silently accepting a save that never happened.
        if save_file_offered and not save_file_called and not nudged:
            nudged = True
            nudge = (
                "You said you would save this, but you never actually called the save_file "
                "tool - no file was written. Call save_file now with the complete text to save."
            )
            print("No save_file call detected on a save-designated step - sending one corrective nudge.")
            log_info("[OLLAMA] NUDGE: save_file was offered but never called - retrying once")
            messages.append({"role": "user", "content": nudge})
            response = ask_local_llm(messages, tools_schema)
            messages.append(response.model_dump())
            log_info(f"[OLLAMA] AGENT RESPONSE: {response}")
            continue

        break

    return response.content


def main():
    messages = load_memory(filepath=MEMORY_FILE)

    # load_memory()'s FileNotFoundError fallback returns a generic default
    # system message - swap it for our own (which carries the save_file
    # safety instruction) so first-run behavior matches every other run.
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    else:
        messages[0]["content"] = SYSTEM_PROMPT

    question = input("Do you like to know weather of any city?\n")
    while question != "":
        steps = create_local_plan(question, conversation_history=messages)
        print("\nPLAN:")
        for s in steps:
            print(f"  {s['step']}. {s['description']}")

        results = []
        for i, step in enumerate(steps):
            step_tools = select_tools_for_step(step["description"])
            step_prompt = f"""
                    Current step: {step['description']}
                    Results so far: {results}
                    Decide which tool, if any, to use for this step.
                """
            try:
                answer = run(messages, step_prompt, tools_schema=step_tools)
                results.append({"step": step["description"], "result": answer})
                save_memory(
                    {"Completed STEP": i + 1, "Results": results},
                    f"memory/ollama_checkpoint_{i + 1}.json"
                )
            except Exception as e:
                log_info(f"[OLLAMA] Step {i + 1} failed: {e}")
                break

        print("\nWEATHER AGENT OUTPUT:")
        for r in results:
            print(f"  Step: {r['step']}\n  Result: {r['result']}\n")

        save_memory(messages, filepath=MEMORY_FILE)  # persist after every turn, not just at exit

        question = input("Anything else you'd like to know about?\n")


if __name__ == "__main__":
    main()
