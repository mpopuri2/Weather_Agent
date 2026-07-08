import ast, operator

ALLOWED_OPS = {ast.Add: operator.add, ast.Sub: operator.sub,
               ast.Mult: operator.mul, ast.Div: operator.truediv}

def safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        return ALLOWED_OPS[type(node.op)](safe_eval(node.left), safe_eval(node.right))
    if isinstance(node, ast.Call) and node.func.id in ("min", "max", "abs"):
        return {"min": min, "max": max, "abs": abs}[node.func.id](*[safe_eval(a) for a in node.args])
    raise ValueError("Unsupported or unsafe expression")

def calculator(expression: str):
    try:
        tree = ast.parse(expression, mode="eval").body
        return str(safe_eval(tree))
    except Exception as e:
        return f"Error: {e}"