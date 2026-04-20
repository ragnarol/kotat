from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base_agent import BaseAgent

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
