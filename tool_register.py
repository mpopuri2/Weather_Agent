from tools.weather_tool import get_weather
from tools.calculator import calculator
from tools.save_file import save_file


import time

TOOLS = {
    "get_weather" : get_weather,
    "calculator" : calculator,
    "save_file" : save_file
}


RISKY_TOOLS = {"save_file"}

def confirm_tool_with_user(tool_name, args):
    if tool_name in RISKY_TOOLS:
        user_decision = input(f"⚠️ Assistant wants to run {tool_name} with args = {args}. Approve (y/n)?\n")
        return user_decision.lower() == "y"
    return True


def execute_tool_safely(tool_function, args, retries = 2, timeout = 5):
    for attempt in range(retries):
        try:
            return tool_function(**args)
        except Exception as e:
            if attempt == retries -1:
                return f"Tool failed after {retries} attempts: {e}"
        time.sleep(1)



