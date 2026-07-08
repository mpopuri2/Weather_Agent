import json
import os

MAX_MESSAGES = 5

def save_memory(messages, filepath = "memory/session.json"):

    if not os.path.exists("memory"):
        os.makedirs("memory")
    
    with open(filepath, "w") as f:
            json.dump(messages, f, indent=2, default=str)
        
    

def load_memory(filepath = "memory/session.json"):
    try:
        with open(filepath, "r") as f:
            messages = json.load(f)
            if len(messages) > MAX_MESSAGES:
                 return [messages[0], *messages[-MAX_MESSAGES: ]]
            else:
                 return messages
    except FileNotFoundError:
        return [{
            "role" : "system", "content" : "You are an helpful weather assistant."
        }]