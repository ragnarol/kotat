from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START
from langgraph.checkpoint.memory import MemorySaver

from models.game_state import GameState
from agents.gm_agent import GameMaster
from agents.player_agent import Player

class DNDAdventure:
    """Orchestrates the game flow, graph construction, and runtime loop."""
    
    def __init__(self, llm_model: str = "gemini-3-flash-preview"):
        self.llm = ChatGoogleGenerativeAI(model=llm_model, temperature=0.7)
        self.memory = MemorySaver()
        
        # Initialize Agents
        self.gm = GameMaster(self.llm)
        self.thief = Player("Shadow", "Shadow", self.llm)
        
        # Build Workflow
        self.app = self._compile_workflow()

    def _compile_workflow(self):
        workflow = StateGraph(GameState)
        
        # Add nodes using the agent's run methods
        workflow.add_node("gm", self.gm.run)
        workflow.add_node("thief", self.thief.run)

        # Define Edges
        workflow.add_edge(START, "gm")
        workflow.add_conditional_edges(
            "gm", 
            lambda state: state["next_player"], 
            {"thief": "thief", "gm": "gm"}
        )
        workflow.add_edge("thief", "gm")

        return workflow.compile(checkpointer=self.memory, interrupt_before=["gm"])

    def start(self, initial_state: GameState, thread_id: str = "game_1"):
        """Starts the adventure loop."""
        config = {"configurable": {"thread_id": thread_id}}
        
        print("--- ADVENTURE START ---")
        self.app.invoke(initial_state, config)

        try:
            while True:
                state = self.app.get_state(config)
                
                # Check if we are interrupted before the GM node
                if "gm" in state.next:
                    print("
" + "="*40)
                    user_input = input("HUMAN OVERRIDE (Enter to continue, or type instructions, 'exit' to quit): ")
                    
                    if user_input.strip().lower() == "exit":
                        break
                        
                    if user_input.strip():
                        # Inject system note/voice of god
                        self.app.update_state(config, {"messages": [HumanMessage(content=f"[System Note: {user_input}]")]})
                    
                    # Stream the updates from the agents
                    for event in self.app.stream(None, config, stream_mode="updates"):
                        for node_name, node_update in event.items():
                            print(f"
[{node_name.upper()}]")
                            if "messages" in node_update:
                                print(node_update["messages"][-1].content)
                else:
                    # Initial trigger or resume if not at GM
                    self.app.invoke(None, config)
        except KeyboardInterrupt:
            print("
Adventure paused.")
