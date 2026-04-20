import os
import operator
from typing import Annotated, List, TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.checkpoint.memory import MemorySaver

# 1. Setup
llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", temperature=0.7)
memory = MemorySaver()

class GameState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_player: str

# 2. Nodes
def gm_node(state):
    # 1. Clean up the history for the GM
    # We want the GM to see the Thief's message as an 'Action' to resolve.
    history = state["messages"]
    
    # 2. The 'Referee Poke'
    # We add a specific instruction at the end so the GM knows to respond.
    prompt = [
        SystemMessage(content="""You are the Game Master for a Red Box D&D game. 
        Your job is to describe the results of player actions and narrate the world. 
        Check for traps, rolls, or monster reactions as needed."""),
        *history,
        HumanMessage(content="[GM: Resolve the player's action and describe what happens next.]")
    ]
    
    # 3. Call Gemini
    response = llm.invoke(prompt)
    response.name = "GameMaster"
    
    return {"messages": [response], "next_player": "thief"}

def thief_node(state):
    # 1. Format the history so the Thief knows the GM is 'The World'
    formatted_history = []
    for msg in state["messages"]:
        if isinstance(msg, AIMessage) and msg.name != "Shadow":
            # Treat other AI messages (GM) as descriptions for the Thief
            formatted_history.append(HumanMessage(content=msg.content, name="GM"))
        else:
            formatted_history.append(msg)

    # 2. Add a very specific 'Call to Action' at the end
    prompt = [
        SystemMessage(content="You are Shadow, a Thief. Respond to the GM's last description in character."),
        *formatted_history,
        HumanMessage(content="Shadow, what do you do?") # The 'Poke'
    ]
    
    # 3. Call Gemini
    response = llm.invoke(prompt)
    
    # Ensure the response has a name so we can distinguish it later
    response.name = "Shadow"
    
    return {"messages": [response], "next_player": "gm"}

# 3. Graph Construction
workflow = StateGraph(GameState)
workflow.add_node("gm", gm_node)
workflow.add_node("thief", thief_node)

workflow.add_edge(START, "gm")
# Use a direct edge from Thief to GM, and conditional from GM to Thief
workflow.add_conditional_edges("gm", lambda x: x["next_player"], {"thief": "thief", "gm": "gm"})
workflow.add_edge("thief", "gm")

# 4. COMPILE WITH INTERRUPT
# We interrupt BEFORE the GM node
app = workflow.compile(checkpointer=memory, interrupt_before=["gm"])

# 5. THE RUN LOOP
config = {"configurable": {"thread_id": "game_1"}}

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

# The FIRST move
print("--- ADVENTURE START ---")
app.invoke(initial_input, config)

while True:
    state = app.get_state(config)
    
    if "gm" in state.next:
        print("\n" + "="*40)
        user_input = input("HUMAN OVERRIDE (Enter to continue, or type instructions): ")
        
        if user_input.strip().lower() == "exit":
            break
            
        if user_input.strip():
            # Voice of God intervention
            app.update_state(config, {"messages": [HumanMessage(content=f"[System Note: {user_input}]")]})
        
        # RESUME AND WATCH THE FLOW
        # We use stream so we can see the Thief and GM actually talk
        for event in app.stream(None, config, stream_mode="updates"):
            for node_name, node_update in event.items():
                print(f"\n[{node_name.upper()}]")
                if "messages" in node_update:
                    # Print the last message added by that node
                    print(node_update["messages"][-1].content)
    else:
        # This catches the start or any unexpected stops
        app.invoke(None, config)