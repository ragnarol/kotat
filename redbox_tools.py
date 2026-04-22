from langchain_core.tools import tool
import random

@tool
def roll_dice(sides: int, reason: str, bonus: int = 0):
    """Rolls a virtual die for the D&D game. 'reason' is mandatory to explain why the roll is happening."""
    result = random.randint(1, sides) + bonus
    return f"Rolled {sides}-sided die for '{reason}'. Result: {result}"

def create_redbox_tools(state_manager):
    @tool
    def pass_time(minutes: int):
        """Advances the game time by a specified number of minutes."""
        events = state_manager.advance_time(minutes)
        msg = f"Time advanced by {minutes} minutes. Current time: {state_manager.get_time_string()}"
        if events:
            msg += "\nEvents:\n- " + "\n- ".join(events)
        return msg

    @tool
    def modify_hp(name: str, amount: int):
        """Applies damage (negative) or healing (positive) to a character."""
        return state_manager.apply_hp_change(name, amount)

    @tool
    def inspect_inventory(name: str):
        """Returns the current inventory of a player character."""
        if name in state_manager.characters:
            char = state_manager.characters[name]
            return f"{name}'s Inventory: {', '.join(char.inventory) if char.inventory else 'Empty'}"
        return f"Character {name} not found."

    @tool
    def attack_roll(attacker_name: str, target_ac: int, attack_mod: int):
        """Perform an attack roll. Success if d20 + mod + target_ac >= 20."""
        roll = random.randint(1, 20)
        total = roll + attack_mod + target_ac
        success = total >= 20
        status = "HIT" if success else "MISS"
        return f"{attacker_name} rolls {roll} + {attack_mod:+} against AC {target_ac} (Total: {total}). Result: {status}"

    @tool
    def damage_roll(attacker_name: str, die_sides: int, damage_mod: int):
        """Perform a damage roll. Rolls a die of specified sides and adds the damage modifier."""
        roll = random.randint(1, die_sides)
        total = max(1, roll + damage_mod)
        return f"{attacker_name} deals {roll} + {damage_mod:+} = {total} damage (using d{die_sides})."

    @tool
    def add_item(character_name: str, item: str):
        """Adds an item to a character's inventory."""
        return state_manager.add_item(character_name, item)

    @tool
    def remove_item(character_name: str, item: str):
        """Removes an item from a character's inventory."""
        return state_manager.remove_item(character_name, item)

    @tool
    def update_location(level: str, room: str):
        """Updates the party's current location in the dungeon (e.g., Level 1, Room 4)."""
        return state_manager.update_location(level, room)

    @tool
    def record_defeat(creature_name: str):
        """Records that a creature has been defeated at the current location."""
        return state_manager.record_defeat(creature_name)

    @tool
    def record_loot(item_name: str, character_name: str):
        """Records that loot was taken by a character at the current location."""
        return state_manager.record_loot(item_name, character_name)

    @tool
    def add_effect(character_name: str, effect_name: str, duration_minutes: int):
        """Adds a temporary effect/condition to a character with a specific duration."""
        return state_manager.add_effect(character_name, effect_name, duration_minutes)

    @tool
    def use_power(character_name: str, power_name: str):
        """Records that a character has used a limited power or spell, consuming it."""
        return state_manager.use_power(character_name, power_name)

    @tool
    def refresh_powers(character_name: str):
        """Refreshes all daily powers and spells for a character (e.g., after a long rest)."""
        return state_manager.refresh_powers(character_name)

    return [pass_time, modify_hp, inspect_inventory, attack_roll, damage_roll, add_item, remove_item, 
            update_location, record_defeat, record_loot, add_effect, use_power, refresh_powers]
