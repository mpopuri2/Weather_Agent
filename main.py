from agent import WeatherAgent

from planner import create_plan
from memory import save_memory, load_memory

obj = WeatherAgent(load_memory())
question = input("Do you like to know weather of any city?\n")
i=0

while question != "":
    i+=1
    
    steps = create_plan(question, conversation_history = obj.messages)
    print(f"\nPLAN:")
    for s in steps:
        print(f"  {s['step']}. {s['description']}")
    results = obj.execute_plan(steps)

    # print(results)


    print(f"\nWEATHER AGENT OUTPUT :")
    for r in results:
        print(f"  Step: {r['step']}\n  Result: {r['result']}\n")
    
    print(f"\n -----------------------------PROMPT {i} ENDED-----------------------------")
   
    print("\nAnyhting else you like to know about?\n")
    question = input()

save_memory(obj.messages)

print(f"\n ----------------------------- CHAT {i} ENDED-----------------------------")
