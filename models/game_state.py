import operator
from typing import Annotated, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

class CharacterData(TypedDict):
    name: str
    max_hp: int
    current_hp: int
    ac: int
    attack_mod: int
    damage_mod: int
    save_target: int
    inventory: List[str]
    effects: Dict[str, int] # effect_name: expiration_total_minutes
    powers: List[str]
    daily_powers: List[str]

class GameState(TypedDict):
    """Represents the state of the game session, persisted by LangGraph."""
    messages: Annotated[List[BaseMessage], operator.add]
    next_player: str
    
    # State Manager data moved here for persistence
    total_minutes: int
    characters: Dict[str, CharacterData]
    current_level: str
    current_room: str
    room_states: Dict[str, str]
    defeated_creatures: List[Dict[str, str]]
    taken_loot: List[Dict[str, str]]
    
    # Legacy/Extra
    dungeon_turn: int
