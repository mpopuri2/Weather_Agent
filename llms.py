
from config import client

tools = [
    {
        "type" : "function",
        "function" : {
            "name" : "get_weather",
            "description" : "Function is useful for retrieving the weather of a city",
            "parameters" : {
                "type" : "object",
                "properties" : {
                    "city" : {
                        "type" : "string",
                        "description" : "name of the city"
                    }
                }
            },
            "required" : ["city"]
        }
    },

    {

        "type" : "function",
        "function" : {
            "name" : "calculator",
            "description" : (
            "Evaluates a SINGLE Python math expression and returns one numeric result. "
            "Must be one valid expression — do NOT use semicolons or multiple statements. "
            "Example: 'max(69, 64, 83) - min(69, 64, 83)' to get a difference in one call."
        ),
            "parameters" : {
                "type" : "object",
                "properties" : {
                    "expression" : {
                        "type" : "string",
                        "description" : "mathematical expression to evaluate example: (2+(3*4)))"
                    }
                }
            },
            "required" : ["expression"]
        }
    },

    {
        "type" : "function",
        "function" : {
            "name" : "save_file",
            "description" : "Function is useful for saving content to a file.",
            "parameters" : {
                "type" : "object",
                "properties" : {
                    "text" : {
                        "type" : "string",
                        "description" : "text to save to the file"
                    }
                }
            },
            "required" : ["text"]
        }
    }
    
]


def ask_llm(messages):
    response = client.chat.completions.create(
        model = "gpt-4.1",
        messages = messages,
        tools = tools,
    )
    return response.choices[0].message

        # temperature = 0.1,
        # max_tokens = 500

def ask_llm_with_no_tool(messages):
    response = client.chat.completions.create(
        model = "gpt-4.1",
        messages = messages
    )
    return response.choices[0].message
