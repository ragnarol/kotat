from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from agents.base_agent import BaseAgent

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
