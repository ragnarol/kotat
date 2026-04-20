import os
import operator
from abc import ABC, abstractmethod
from typing import Annotated, List, TypedDict, Optional, Union, Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.checkpoint.memory import MemorySaver

# --- State Definition ---
class GameState(TypedDict):
    """Represents the state of the game session."""
    messages: Annotated[List[BaseMessage], operator.add]
    next_player: str
    dungeon_turn: int
    inventory: Dict[str, List[str]]

# --- Agent Base Classes ---
class BaseAgent(ABC):
    """Abstract base class for all game agents (GM, Players, NPCs)."""
    
    def __init__(self, name: str, llm: ChatGoogleGenerativeAI):
        self.name = name
        self.llm = llm

    @abstractmethod
    def _get_system_message(self) -> SystemMessage:
        """Returns the system instructions for this agent."""
        pass

    @abstractmethod
    def _get_poke_message(self) -> HumanMessage:
        """Returns the 'poke' message that triggers the agent's turn."""
        pass

    def _preprocess_history(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Optionally modify the message history before it's sent to the LLM."""
        return messages

    @abstractmethod
    def get_next_player_id(self) -> str:
        """Returns the ID of the node that should follow this agent."""
        pass

    def run(self, state: GameState) -> Dict[str, Any]:
        """Executes the agent's turn logic."""
        history = self._preprocess_history(state["messages"])
        
        prompt = [
            self._get_system_message(),
            *history,
            self._get_poke_message()
        ]
        
        response = self.llm.invoke(prompt)
        response.name = self.name
        
        return {
            "messages": [response],
            "next_player": self.get_next_player_id()
        }

# --- Concrete Agent Implementations ---
class GameMaster(BaseAgent):
    """The Game Master agent responsible for world narration and action resolution."""
    
    def __init__(self, llm: ChatGoogleGenerativeAI):
        super().__init__("GameMaster", llm)

    def _get_system_message(self) -> SystemMessage:
        return SystemMessage(content="""You are the Game Master for a Red Box D&D game. 
        Your job is to describe the results of player actions and narrate the world. 
        Check for traps, rolls, or monster reactions as needed.""")

    def _get_poke_message(self) -> HumanMessage:
        return HumanMessage(content="[GM: Resolve the player's action and describe what happens next.]")

    def get_next_player_id(self) -> str:
        return "thief"

class Player(BaseAgent):
    """A player-controlled (or simulated) character agent."""
    
    def __init__(self, agent_id: str, character_name: str, llm: ChatGoogleGenerativeAI, next_player: str = "gm"):
        super().__init__(agent_id, llm)
        self.character_name = character_name
        self.next_player = next_player

    def _preprocess_history(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Format history so the player sees the GM as 'the world'."""
        formatted_history = []
        for msg in messages:
            # If the message is from an AI but not this character, treat it as GM description
            if isinstance(msg, AIMessage) and msg.name != self.name:
                formatted_history.append(HumanMessage(content=msg.content, name="GM"))
            else:
                formatted_history.append(msg)
        return formatted_history

    def _get_system_message(self) -> SystemMessage:
        return SystemMessage(content=f"You are {self.character_name}. Respond to the GM's last description in character.")

    def _get_poke_message(self) -> HumanMessage:
        return HumanMessage(content=f"{self.character_name}, what do you do?")

    def get_next_player_id(self) -> str:
        return self.next_player

# --- Game Engine ---
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
                    print("\n" + "="*40)
                    user_input = input("HUMAN OVERRIDE (Enter to continue, or type instructions, 'exit' to quit): ")
                    
                    if user_input.strip().lower() == "exit":
                        break
                        
                    if user_input.strip():
                        # Inject system note/voice of god
                        self.app.update_state(config, {"messages": [HumanMessage(content=f"[System Note: {user_input}]")]})
                    
                    # Stream the updates from the agents
                    for event in self.app.stream(None, config, stream_mode="updates"):
                        for node_name, node_update in event.items():
                            print(f"\n[{node_name.upper()}]")
                            if "messages" in node_update:
                                print(node_update["messages"][-1].content)
                else:
                    # Initial trigger or resume if not at GM
                    self.app.invoke(None, config)
        except KeyboardInterrupt:
            print("\nAdventure paused.")

# --- Entry Point ---
if __name__ == "__main__":
    adventure = DNDAdventure()
    
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
        "next_player": "gm",
        "dungeon_turn": 1,
        "inventory": {"Fighter": ["Longsword", "Shield"], "Thief": ["Dagger", "Lockpicks"]}
    }
    
    adventure.start(initial_input)
