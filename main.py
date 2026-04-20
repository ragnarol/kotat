from langchain_core.messages import HumanMessage
from adventure import DNDAdventure

def main():
    adventure = DNDAdventure()
    
    initial_input = {
        "messages": [
            HumanMessage(content="""
                The game begins! 
                Setting: The entrance of the 'Caves of Chaos'. 
                Party: 
                - Shadow (Thief)
                
                GM, please describe the entrance and ask for actions.
            """)
        ],
        "next_player": "gm",
        "dungeon_turn": 1,
        "inventory": {"Fighter": ["Longsword", "Shield"], "Thief": ["Dagger", "Lockpicks"]}
    }
    
    adventure.start(initial_input)

if __name__ == "__main__":
    main()
