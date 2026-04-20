from typing import TypedDict
from langgraph.graph import StateGraph, START, END

# 1. Define the State
class State(TypedDict):
    message: str

# 2. Define a Node (Logic)
def my_node(state: State):
    print(f"---Processing: {state['message']}---")
    return {"message": state['message'] + " ...and processed!"}

# 3. Build the Graph
builder = StateGraph(State)
builder.add_node("logic", my_node)
builder.add_edge(START, "logic")
builder.add_edge("logic", END)

graph = builder.compile()

# 4. Run it
result = graph.invoke({"message": "Hello from the container"})
print(result)