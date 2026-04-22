from typing import Dict, Any, List

class CharacterSheet:
    def __init__(self, name: str, max_hp: int, ac: int, attack_mod: int, save_target: int):
        self.name = name
        self.max_hp = max_hp
        self.current_hp = max_hp
        self.ac = ac  # Red Box style: lower is better
        self.attack_mod = attack_mod
        self.save_target = save_target
        self.inventory: List[str] = []

    def to_status_line(self) -> str:
        return f"{self.name}: HP {self.current_hp}/{self.max_hp}, AC {self.ac}, Atk {self.attack_mod:+} Save {self.save_target}"

class StateManager:
    """Service to manage global game state like time, calendar, and character sheets."""
    
    def __init__(self, start_hour: int = 8, start_minute: int = 0):
        self.total_minutes = start_hour * 60 + start_minute
        self.characters: Dict[str, CharacterSheet] = {}

    def add_character(self, name: str, max_hp: int, ac: int, attack_mod: int, save_target: int):
        self.characters[name] = CharacterSheet(name, max_hp, ac, attack_mod, save_target)

    def advance_time(self, minutes: int):
        self.total_minutes += minutes

    def get_time_string(self) -> str:
        hours = (self.total_minutes // 60) % 24
        minutes = self.total_minutes % 60
        return f"{hours:02d}:{minutes:02d}"

    def get_party_status(self) -> str:
        return " | ".join([c.to_status_line() for c in self.characters.values()])

    def apply_hp_change(self, name: str, amount: int):
        if name in self.characters:
            char = self.characters[name]
            char.current_hp = max(0, min(char.max_hp, char.current_hp + amount))
            return f"{name} HP is now {char.current_hp}/{char.max_hp}"
        return f"Character {name} not found."

    def __str__(self):
        return f"Time: {self.get_time_string()} | Party: {self.get_party_status()}"
