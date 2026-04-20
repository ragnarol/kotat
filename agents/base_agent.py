from abc import ABC, abstractmethod
from typing import List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from models.game_state import GameState

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
