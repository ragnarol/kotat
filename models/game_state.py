import operator
from typing import Annotated, List, Dict, Any
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

class GameState(TypedDict):
    """Represents the state of the game session."""
    messages: Annotated[List[BaseMessage], operator.add]
    next_player: str
    dungeon_turn: int
    inventory: Dict[str, List[str]]
