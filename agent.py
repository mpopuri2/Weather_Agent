import json
import datetime
from log import log_info

from llms import ask_llm
from tool_register import TOOLS, confirm_tool_with_user, execute_tool_safely

from memory import save_memory

class WeatherAgent:
    def __init__(self, old_messages):
        self.messages = old_messages
        

    def run(self, question):
        
        self.messages.append({"role" : "user","content" : question})
        log_info(f"USER REQUEST: {question}")

        response = ask_llm(self.messages)
        self.messages.append(response.model_dump())
        log_info(f"AGENT RESPONSE: {response}")

        while response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.function.name

                args = json.loads(tool_call.function.arguments)

                tool_function = TOOLS[tool_name]
                #print(f"ACTUALLY CALLING TOOL: {tool_name} with args {args}")   # temp debug
                log_info(f"TOOL CALL: {tool_name} args={args}")
                if not confirm_tool_with_user(tool_name, args):
                    result = f"ACTION DECLINED BY USER: {tool_name} was not executed."
                else:
                    result = execute_tool_safely(tool_function, args)
                log_info(f"TOOL RESULT: {result}")
                self.messages.append(
                    {
                        "role" : "tool",
                        "tool_call_id" : tool_call.id,
                        "content" : result
                    }
                )
            

            response = ask_llm(self.messages)
            self.messages.append(response.model_dump())
            log_info(f"AGENT RESPONSE: {response}")
        return response.content
    
    def execute_plan(self,steps):
        results=[]
        for i, step in enumerate(steps):
            try:
                step_prompt = f"""
                        Current step: {step["description"]}
                        Results so far: {results}
                        Decide which tools or any to use for this step.
                    """
                result = self.run(step_prompt)
                results.append({"step": step['description'], "result" : result})
                save_memory({"Completed STEP" : i+1, "Results" : results}, f"memory/checkpoint_{i+1}.json")
            except Exception as e:
                log_info(f"Step {i+1} failed: {e}")
                break 

        return results



        # return response
    