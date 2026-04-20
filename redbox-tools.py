from langchain_core.tools import tool

@tool
def roll_dice(sides: int, bonus: int = 0):
    """Rolls a virtual die for the D&D game."""
    import random
    result = random.randint(1, sides) + bonus
    return f"Rolled {sides}-sided die. Result: {result}"
