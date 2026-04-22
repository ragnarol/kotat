from typing import Dict, Any, List
from models.game_state import GameState, CharacterData

class CharacterHelper:
    """Helper to provide status strings for characters stored in GameState."""
    @staticmethod
    def to_status_line(char: CharacterData) -> str:
        status = f"{char['name']}: HP {char['current_hp']}/{char['max_hp']}, AC {char['ac']}, Atk {char['attack_mod']:+}, Dmg {char['damage_mod']:+}, Save {char['save_target']}"
        if char['effects']:
            effects_str = ", ".join(char['effects'].keys())
            status += f" [Effects: {effects_str}]"
        if char['powers']:
            powers_str = ", ".join(char['powers'])
            status += f" [Powers: {powers_str}]"
        return status

class StateManager:
    """Service to manage global game state by operating on a GameState object."""
    
    def __init__(self, state: GameState):
        self.state = state

    def add_character(self, name: str, max_hp: int, ac: int, attack_mod: int, damage_mod: int, save_target: int):
        self.state['characters'][name] = {
            "name": name,
            "max_hp": max_hp,
            "current_hp": max_hp,
            "ac": ac,
            "attack_mod": attack_mod,
            "damage_mod": damage_mod,
            "save_target": save_target,
            "inventory": [],
            "effects": {},
            "powers": [],
            "daily_powers": []
        }

    def use_power(self, character_name: str, power_name: str):
        if character_name in self.state['characters']:
            char = self.state['characters'][character_name]
            if power_name in char['powers']:
                char['powers'].remove(power_name)
                return f"{character_name} used power: {power_name}. Remaining: {', '.join(char['powers']) if char['powers'] else 'None'}"
            return f"Power '{power_name}' not available for {character_name}."
        return f"Character {character_name} not found."

    def refresh_powers(self, character_name: str):
        if character_name in self.state['characters']:
            char = self.state['characters'][character_name]
            char['powers'] = list(char['daily_powers'])
            return f"{character_name}'s powers have been refreshed: {', '.join(char['powers'])}"
        return f"Character {character_name} not found."

    def advance_time(self, minutes: int) -> List[str]:
        """Increases the current time and returns a list of events (like expired effects)."""
        self.state['total_minutes'] += minutes
        events = []
        
        for char_name, char in self.state['characters'].items():
            expired = []
            for effect_name, expiration in char['effects'].items():
                if self.state['total_minutes'] >= expiration:
                    expired.append(effect_name)
            
            for effect_name in expired:
                del char['effects'][effect_name]
                events.append(f"Effect '{effect_name}' has expired on {char_name}.")
                
        return events

    def add_effect(self, character_name: str, effect_name: str, duration_minutes: int):
        if character_name in self.state['characters']:
            expiration = self.state['total_minutes'] + duration_minutes
            self.state['characters'][character_name]['effects'][effect_name] = expiration
            return f"Added effect '{effect_name}' to {character_name} for {duration_minutes} minutes (expires at {self._format_time(expiration)})."
        return f"Character {character_name} not found."

    def _format_time(self, total_mins: int) -> str:
        hours = (total_mins // 60) % 24
        minutes = total_mins % 60
        return f"{hours:02d}:{minutes:02d}"

    def get_time_string(self) -> str:
        return self._format_time(self.state['total_minutes'])

    def get_party_status(self) -> str:
        loc = f"Location: {self.state['current_level']}, {self.state['current_room']}"
        chars = " | ".join([CharacterHelper.to_status_line(c) for c in self.state['characters'].values()])
        return f"{loc} | {chars}"

    def apply_hp_change(self, name: str, amount: int):
        if name in self.state['characters']:
            char = self.state['characters'][name]
            char['current_hp'] = max(0, min(char['max_hp'], char['current_hp'] + amount))
            return f"{name} HP is now {char['current_hp']}/{char['max_hp']}"
        return f"Character {name} not found."

    def add_item(self, character_name: str, item: str):
        if character_name in self.state['characters']:
            self.state['characters'][character_name]['inventory'].append(item)
            return f"Added '{item}' to {character_name}'s inventory."
        return f"Character {character_name} not found."

    def remove_item(self, character_name: str, item: str):
        if character_name in self.state['characters']:
            char = self.state['characters'][character_name]
            if item in char['inventory']:
                char['inventory'].remove(item)
                return f"Removed '{item}' from {character_name}'s inventory."
            return f"Item '{item}' not found in {character_name}'s inventory."
        return f"Character {character_name} not found."

    def update_location(self, level: str, room: str):
        self.state['current_level'] = level
        self.state['current_room'] = room
        return f"Location updated: {level}, {room}"

    def get_room_state(self, level: str, room: str) -> str:
        key = f"{level}|{room}"
        return self.state['room_states'].get(key, "Original state (no modifications).")

    def update_room_state(self, level: str, room: str, state_description: str):
        key = f"{level}|{room}"
        self.state['room_states'][key] = state_description
        return f"Room state updated for {level}, {room}: {state_description}"

    def record_defeat(self, creature_name: str):
        entry = {
            "creature": creature_name,
            "level": self.state['current_level'],
            "room": self.state['current_room'],
            "time": self.get_time_string()
        }
        self.state['defeated_creatures'].append(entry)
        return f"Recorded defeat of {creature_name} at {self.state['current_level']}, {self.state['current_room']}."

    def record_loot(self, item_name: str, character_name: str):
        if character_name in self.state['characters']:
            self.state['characters'][character_name]['inventory'].append(item_name)
            entry = {
                "item": item_name,
                "taken_by": character_name,
                "level": self.state['current_level'],
                "room": self.state['current_room'],
                "time": self.get_time_string()
            }
            self.state['taken_loot'].append(entry)
            return f"Recorded '{item_name}' taken by {character_name} at {self.state['current_level']}, {self.state['current_room']}."
        return f"Character {character_name} not found."

    def __str__(self):
        return f"Time: {self.get_time_string()} | {self.get_party_status()}"
