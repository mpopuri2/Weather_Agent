def execute_plan(steps, agent):
    results=[]
    for step in steps:
        step_prompt = f"""
                Current step: {step["description"]}
                Results so far: {results}
                Decide which tools or any any to use for this step.
            """
        result = agent.run(step_prompt)
        results.append({"step": step['description'], "result" : result})
    return results