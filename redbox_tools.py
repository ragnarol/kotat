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
        state_manager.advance_time(minutes)
        return f"Time advanced by {minutes} minutes. Current time: {state_manager.get_time_string()}"

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

    return [pass_time, modify_hp, inspect_inventory, attack_roll]
