import sys
import os
from langchain_core.messages import HumanMessage
from adventure import DNDAdventure

def main():
    if len(sys.argv) > 1:
        data_path = sys.argv[1]
    else:
        data_path = input("Enter the path to the adventure folder (e.g., 'stonehell'): ").strip()
        if not data_path:
            data_path = "stonehell"

    if not os.path.exists(data_path):
        print(f"Error: Folder '{data_path}' does not exist.")
        return

    adventure = DNDAdventure(data_path=data_path)
    
    # Construct party description for the initial prompt
    party_desc = "\n".join([f"- {p.character_name}: {p.character_description}" for p in adventure.players])
    
    initial_input = {
        "messages": [
            HumanMessage(content=f"""
                The game begins! 
                Adventure Context: {adventure.adventure_context}
                
                Party: 
                {party_desc}
                
                GM, please describe the entrance and ask for actions.
            """)
        ],
        "next_player": "gm",
        "dungeon_turn": 1,
        "inventory": {p.character_name: [] for p in adventure.players}
    }
    
    adventure.start(initial_input)

if __name__ == "__main__":
    main()
