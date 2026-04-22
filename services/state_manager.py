from typing import Dict, Any, List

class CharacterSheet:
    def __init__(self, name: str, max_hp: int, ac: int, attack_mod: int, damage_mod: int, save_target: int):
        self.name = name
        self.max_hp = max_hp
        self.current_hp = max_hp
        self.ac = ac  # Red Box style: lower is better
        self.attack_mod = attack_mod
        self.damage_mod = damage_mod
        self.save_target = save_target
        self.inventory: List[str] = []
        self.effects: Dict[str, int] = {} # effect_name: expiration_total_minutes
        self.powers: List[str] = []
        self.daily_powers: List[str] = [] # Master list for refreshing

    def to_status_line(self) -> str:
        status = f"{self.name}: HP {self.current_hp}/{self.max_hp}, AC {self.ac}, Atk {self.attack_mod:+}, Dmg {self.damage_mod:+}, Save {self.save_target}"
        if self.effects:
            effects_str = ", ".join(self.effects.keys())
            status += f" [Effects: {effects_str}]"
        if self.powers:
            powers_str = ", ".join(self.powers)
            status += f" [Powers: {powers_str}]"
        return status

class StateManager:
    """Service to manage global game state like time, calendar, and character sheets."""
    
    def __init__(self, start_hour: int = 8, start_minute: int = 0):
        self.total_minutes = start_hour * 60 + start_minute
        self.characters: Dict[str, CharacterSheet] = {}
        
        # Location tracking
        self.current_level = "Unknown Level"
        self.current_room = "Entrance"
        
        # Kill and Loot logs
        self.defeated_creatures: List[Dict[str, str]] = []
        self.taken_loot: List[Dict[str, str]] = []

    def add_character(self, name: str, max_hp: int, ac: int, attack_mod: int, damage_mod: int, save_target: int):
        self.characters[name] = CharacterSheet(name, max_hp, ac, attack_mod, damage_mod, save_target)

    def use_power(self, character_name: str, power_name: str):
        if character_name in self.characters:
            char = self.characters[character_name]
            if power_name in char.powers:
                char.powers.remove(power_name)
                return f"{character_name} used power: {power_name}. Remaining: {', '.join(char.powers) if char.powers else 'None'}"
            return f"Power '{power_name}' not available for {character_name}."
        return f"Character {character_name} not found."

    def refresh_powers(self, character_name: str):
        if character_name in self.characters:
            char = self.characters[character_name]
            char.powers = list(char.daily_powers)
            return f"{character_name}'s powers have been refreshed: {', '.join(char.powers)}"
        return f"Character {character_name} not found."

    def advance_time(self, minutes: int) -> List[str]:
        """Increases the current time and returns a list of events (like expired effects)."""
        self.total_minutes += minutes
        events = []
        
        for char_name, char in self.characters.items():
            expired = []
            for effect_name, expiration in char.effects.items():
                if self.total_minutes >= expiration:
                    expired.append(effect_name)
            
            for effect_name in expired:
                del char.effects[effect_name]
                events.append(f"Effect '{effect_name}' has expired on {char_name}.")
                
        return events

    def add_effect(self, character_name: str, effect_name: str, duration_minutes: int):
        if character_name in self.characters:
            expiration = self.total_minutes + duration_minutes
            self.characters[character_name].effects[effect_name] = expiration
            return f"Added effect '{effect_name}' to {character_name} for {duration_minutes} minutes (expires at {self._format_time(expiration)})."
        return f"Character {character_name} not found."

    def _format_time(self, total_mins: int) -> str:
        hours = (total_mins // 60) % 24
        minutes = total_mins % 60
        return f"{hours:02d}:{minutes:02d}"

    def get_time_string(self) -> str:
        return self._format_time(self.total_minutes)

    def get_party_status(self) -> str:
        loc = f"Location: {self.current_level}, {self.current_room}"
        chars = " | ".join([c.to_status_line() for c in self.characters.values()])
        return f"{loc} | {chars}"

    def apply_hp_change(self, name: str, amount: int):
        if name in self.characters:
            char = self.characters[name]
            char.current_hp = max(0, min(char.max_hp, char.current_hp + amount))
            return f"{name} HP is now {char.current_hp}/{char.max_hp}"
        return f"Character {name} not found."

    def add_item(self, character_name: str, item: str):
        if character_name in self.characters:
            self.characters[character_name].inventory.append(item)
            return f"Added '{item}' to {character_name}'s inventory."
        return f"Character {character_name} not found."

    def remove_item(self, character_name: str, item: str):
        if character_name in self.characters:
            if item in self.characters[character_name].inventory:
                self.characters[character_name].inventory.remove(item)
                return f"Removed '{item}' from {character_name}'s inventory."
            return f"Item '{item}' not found in {character_name}'s inventory."
        return f"Character {character_name} not found."

    def update_location(self, level: str, room: str):
        self.current_level = level
        self.current_room = room
        return f"Location updated: {level}, {room}"

    def record_defeat(self, creature_name: str):
        entry = {
            "creature": creature_name,
            "level": self.current_level,
            "room": self.current_room,
            "time": self.get_time_string()
        }
        self.defeated_creatures.append(entry)
        return f"Recorded defeat of {creature_name} at {self.current_level}, {self.current_room}."

    def record_loot(self, item_name: str, character_name: str):
        if character_name in self.characters:
            self.characters[character_name].inventory.append(item_name)
            entry = {
                "item": item_name,
                "taken_by": character_name,
                "level": self.current_level,
                "room": self.current_room,
                "time": self.get_time_string()
            }
            self.taken_loot.append(entry)
            return f"Recorded '{item_name}' taken by {character_name} at {self.current_level}, {self.current_room}."
        return f"Character {character_name} not found."

    def __str__(self):
        return f"Time: {self.get_time_string()} | {self.get_party_status()}"
