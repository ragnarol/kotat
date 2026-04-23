from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from models.game_state import GameState

class BaseAgent(ABC):
    """Abstract base class for all game agents (GM, Players, NPCs)."""
    
    def __init__(self, name: str, llm: ChatGoogleGenerativeAI):
        self.name = name
        self.llm = llm
        self.is_cached = False

    @abstractmethod
    def _get_system_message(self, state_manager: Any) -> SystemMessage:
        """Returns the dynamic system instructions for this agent (e.g. current status)."""
        pass

    @abstractmethod
    def get_static_messages(self) -> List[BaseMessage]:
        """Returns the static messages to be used for context caching."""
        return []

    def get_tools(self, state_manager: Any) -> List[Any]:
        """Returns tools for this agent. Overridden by GM."""
        return []

    def set_cached_llm(self, llm: ChatGoogleGenerativeAI):
        """Sets the LLM instance that uses a context cache."""
        self.llm = llm
        self.is_cached = True

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
        # This will be overridden in GM/Player to provide correct state_manager
        raise NotImplementedError("Subclasses must implement run()")
