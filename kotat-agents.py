import os
from typing import Annotated, List, TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START
import operator
 

# 1. Initialize the LLM (Gemini 3 Flash is great for speed/cost)
llm_no_tools = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    temperature=0.7,
)


# Bind the tool to Gemini
# llm = llm_no_tools.bind_tools([roll_dice])
llm = llm_no_tools

class GameState(TypedDict):
    # 'add' means new messages are appended to history rather than overwriting
    messages: Annotated[List[BaseMessage], operator.add]
    next_player: str
    dungeon_turn: int
    inventory: dict


# 2. Define your GM Node
def gm_node(state):
    # The GM looks at the whole chat history
    response = llm.invoke(state["messages"])
    
    # We append the GM's response to the shared message state
    return {
        "messages": [response], 
        "next_player": "thief"  # <--- Make sure this isn't "gm"
    }

# 3. Define the Player Node (Example: The Thief)
def thief_node(state):
    # Prompting the LLM specifically to be the Thief
    character_prompt = [
        SystemMessage(content="You are a level 1 Thief in a Red Box D&D game. Short, punchy dialogue only."),
        *state["messages"] # Include the game history
    ]
    response = llm.invoke(character_prompt)
    return {
        "messages": [response], 
        "next_player": "thief"  # <--- Make sure this isn't "gm"
    }

def router(state):
    next_p = state.get("next_player")
    print(f"--- ROUTING DEBUG: State says next player is '{next_p}' ---")
    return next_p

workflow = StateGraph(GameState)

# Add your agents
workflow.add_node("gm", gm_node)
workflow.add_node("thief", thief_node)
# workflow.add_node("fighter", player_node)

# Define the flow (Logic: GM -> Player -> GM)
workflow.add_edge(START, "gm")

# Conditional routing: Who speaks next?
workflow.add_conditional_edges(
    "gm",
    router,
    # {"thief": "thief", "fighter": "fighter"}
    {"thief": "thief", "gm": "gm"}
)

workflow.add_edge("thief", "gm")
# workflow.add_edge("fighter", "gm")

# Compile the game engine
app = workflow.compile()

# Change your compile line to this:
# app = workflow.compile(interrupt_before=["gm"])


# 1. Setup the initial state
# We tell the GM who the characters are and where they are.
initial_input = {
    "messages": [
        HumanMessage(content="""
            The game begins! 
            Setting: The entrance of the 'Caves of Chaos'. 
            Party: 
            - Shadow (Thief)
            
            GM, please describe the entrance and ask for actions.
        """)
    ],
    "next_player": "gm",  # Ensure the GM starts
    "dungeon_turn": 1,
    "inventory": {"Fighter": ["Longsword", "Shield"], "Thief": ["Dagger", "Lockpicks"]}
}


# # Then run like this:
# thread = {"configurable": {"thread_id": "game_1"}}
# app.invoke(initial_input, thread)

# while True:
#     user_input = input("\n[Press Enter to continue the AI turn, or type 'exit'] ")
#     if user_input.lower() == "exit": break
#     app.invoke(None, thread) # 'None' tells it to resume from where it paused

# 2. Run the loop
# We use .stream so you can see the conversation happen in real-time
print("--- STARTING THE ADVENTURE ---")
for event in app.stream(initial_input):
    for node_name, state_update in event.items():
        # This prints which AI is currently 'thinking'
        print(f"\n[ {node_name.upper()} IS SPEAKING ]")
        
        # Print the last message added to the state
        if "messages" in state_update:
            print(state_update["messages"][-1].content)