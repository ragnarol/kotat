from typing import List, Optional, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from agents.base_agent import BaseAgent

class Player(BaseAgent):
    """A player-controlled (or simulated) character agent."""
    
    def __init__(self, agent_id: str, character_name: str, llm: ChatGoogleGenerativeAI, 
                 state_manager: Any,
                 next_player: str = "gm", 
                 physical_description: Optional[str] = None, 
                 personality_description: Optional[str] = None, 
                 adventure_context: Optional[str] = None):
        super().__init__(agent_id, llm)
        self.character_name = character_name
        self.state_manager = state_manager
        self.next_player = next_player
        self.physical_description = physical_description or ""
        self.personality_description = personality_description or ""
        self.adventure_context = adventure_context or ""

    def _preprocess_history(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        formatted_history = []
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.name != self.name:
                formatted_history.append(HumanMessage(content=msg.content, name="GM"))
            else:
                formatted_history.append(msg)
        return formatted_history

    def _get_system_message(self) -> SystemMessage:
        char = self.state_manager.characters.get(self.character_name)
        status_line = char.to_status_line() if char else "Status Unknown"
        inventory = ", ".join(char.inventory) if char and char.inventory else "Empty"

        content = f"""You are {self.character_name}. Respond to the GM's description in character.
        
        Current Time: {self.state_manager.get_time_string()}
        Your Status: {status_line}
        Your Inventory: {inventory}
        
        Full Party Status: {self.state_manager.get_party_status()}
        
        IMPORTANT ROLEPLAY GUIDELINES:
        1. Describe your actions vividly, but DO NOT roll dice or calculate mechanics (like attack or damage rolls) yourself. The GM will handle all rolls and results.
        2. Be specific about which items from your inventory you are using for your actions.
        3. Respond in character, staying true to your description and behavior guidelines."""
        
        if self.adventure_context:
            content += f"\n\nAdventure Context:\n{self.adventure_context}"
        if self.personality_description:
            content += f"\n\nPersonality Description:\n{self.personality_description}"
        if self.physical_description:
            content += f"\n\nPhysical Description:\n{self.physical_description}"
            
        return SystemMessage(content=content)

    def _get_poke_message(self) -> HumanMessage:
        return HumanMessage(content=f"{self.character_name}, what do you do?")

    def get_next_player_id(self) -> str:
        return self.next_player
