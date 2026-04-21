from typing import Optional, List, Dict, Any
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base_agent import BaseAgent
from models.game_state import GameState

class GameMaster(BaseAgent):
    """The Game Master agent responsible for world narration and action resolution."""
    
    def __init__(self, llm: ChatGoogleGenerativeAI, adventure_context: Optional[str] = None, 
                 player_ids: List[str] = None, adventure_pdf_base64: Optional[str] = None):
        super().__init__("GameMaster", llm)
        self.adventure_context = adventure_context or ""
        self.player_ids = player_ids or []
        self.adventure_pdf_base64 = adventure_pdf_base64
        self._next_player_override = None

    def _get_system_message(self) -> SystemMessage:
        content = """You are the Game Master for a Red Box D&D game. 
        Your job is to describe the results of player actions and narrate the world. 
        Check for traps, rolls, or monster reactions as needed.
        
        At the end of your description, you MUST specify which character should act next by adding '[NEXT: CharacterName]' on a new line.
        Available characters: """ + ", ".join(self.player_ids)
        
        if self.adventure_context:
            content += f"\n\nAdventure Context:\n{self.adventure_context}"
            
        if self.adventure_pdf_base64:
            content += f"\n\nAttached Adventure PDF (Base64):\n{self.adventure_pdf_base64}"
            
        return SystemMessage(content=content)

    def _get_poke_message(self) -> HumanMessage:
        return HumanMessage(content="[GM: Resolve the player's action, describe the scene, and nominate the next player.]")

    def run(self, state: GameState) -> Dict[str, Any]:
        """Executes the GM's turn and extracts the next player."""
        result = super().run(state)
        response_content = result["messages"][0].content
        
        # Handle list-type content (multimodal or block-based responses)
        if isinstance(response_content, list):
            response_text = "".join([
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in response_content
            ])
        else:
            response_text = str(response_content)
        
        # Extract [NEXT: CharacterName]
        match = re.search(r"\[NEXT:\s*([^\]]+)\]", response_text)
        if match:
            next_player = match.group(1).strip()
            # Validate next_player is in player_ids
            if next_player in self.player_ids:
                result["next_player"] = next_player
            else:
                # Fallback to first player if invalid
                result["next_player"] = self.player_ids[0] if self.player_ids else "gm"
        else:
            # Fallback
            result["next_player"] = self.player_ids[0] if self.player_ids else "gm"
            
        return result

    def get_next_player_id(self) -> str:
        # This is used by super().run but we override run anyway to handle the logic
        return "gm"
