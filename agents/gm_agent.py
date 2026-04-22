from typing import Optional, List, Dict, Any
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, ToolMessage
from agents.base_agent import BaseAgent
from models.game_state import GameState
from redbox_tools import roll_dice, create_redbox_tools

class GameMaster(BaseAgent):
    """The Game Master agent responsible for world narration and action resolution."""
    
    def __init__(self, llm: ChatGoogleGenerativeAI, 
                 state_manager: Any,
                 adventure_context: Optional[str] = None, 
                 player_ids: List[str] = None, 
                 adventure_pdf_base64: Optional[str] = None):
        super().__init__("GameMaster", llm)
        self.adventure_context = adventure_context or ""
        self.player_ids = player_ids or []
        self.adventure_pdf_base64 = adventure_pdf_base64
        self.state_manager = state_manager
        
        # Create and bind tools
        self.tools = [roll_dice] + create_redbox_tools(self.state_manager)
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    def _get_system_message(self) -> SystemMessage:
        content = f"""You are the Game Master for a Red Box D&D game. 
        Your job is to describe the results of player actions and narrate the world. 
        Check for traps, rolls, or monster reactions as needed.
        
        Current game time: {self.state_manager.get_time_string()}
        Party Status: {self.state_manager.get_party_status()}
        
        Available tools: {[t.name for t in self.tools]}
        
        Important Guidelines:
        1. PERSISTENT WORLD: Use 'get_room_state' whenever the party enters a room OR when you need to know if something has changed (e.g., is the door still broken?). Use 'update_room_state' to record permanent changes to the environment.
        2. When the party moves to a new area or room, you MUST use the 'update_location' tool.
        3. EXITS: Every time the group reaches a new location (room, chamber, corridor), you MUST describe every door, hallway, or opening leading out of it. Be precise. If there are multiple exits in the same direction (e.g., two doors on the North wall), describe both individually. Never omit an exit.
        4. When a creature is defeated, use the 'record_defeat' tool.
        5. When the party finds and takes loot, use the 'record_loot' tool.
        6. Use 'add_effect' for temporary conditions (e.g., 'Blessed', 'Poisoned', 'Torch Light').
        7. When using 'roll_dice', you MUST provide a 'reason' for the roll.
        
        Red Box Combat: To attack, use attack_roll with target's AC and attacker's mod. 
        Lower AC is harder to hit (-10 to 10).
        
        At the end of your description, you MUST nominate the next player: [NEXT: CharacterName]
        Available characters: {", ".join(self.player_ids)}"""
        
        if self.adventure_context:
            content += f"\n\nAdventure Context:\n{self.adventure_context}"
            
        return SystemMessage(content=content)

    def _preprocess_history(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        processed_messages = list(messages)
        if self.adventure_pdf_base64:
            pdf_context = HumanMessage(
                content=[
                    {"type": "text", "text": "Reference rulebook/adventure PDF for mechanics and setting:"},
                    {"type": "media", "mime_type": "application/pdf", "data": self.adventure_pdf_base64}
                ]
            )
            processed_messages.insert(0, pdf_context)
        return processed_messages

    def _get_poke_message(self) -> HumanMessage:
        return HumanMessage(content="[GM: Resolve actions, describe the scene, nominate next player.]")

    def run(self, state: GameState) -> Dict[str, Any]:
        # Automatically advance time by 1 minute per turn
        expiration_events = self.state_manager.advance_time(1)
        
        history = self._preprocess_history(state["messages"])
        
        # If any effects expired, inform the LLM by prepending a system note to the history
        if expiration_events:
            event_note = "[System Note: " + " ".join(expiration_events) + "]"
            history.append(HumanMessage(content=event_note))

        prompt = [self._get_system_message(), *history, self._get_poke_message()]
        
        all_new_messages = []
        while True:
            response = self.llm_with_tools.invoke(prompt)
            response.name = self.name
            all_new_messages.append(response)
            if not response.tool_calls:
                break
                
            prompt.append(response)
            for tool_call in response.tool_calls:
                tool_to_use = next((t for t in self.tools if t.name == tool_call["name"]), None)
                if tool_to_use:
                    result = tool_to_use.invoke(tool_call["args"])
                    tool_msg = ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                    prompt.append(tool_msg)
                    all_new_messages.append(tool_msg)
                else:
                    tool_msg = ToolMessage(content=f"Error: Tool {tool_call['name']} not found.", tool_call_id=tool_call["id"])
                    prompt.append(tool_msg)
                    all_new_messages.append(tool_msg)

        last_content = all_new_messages[-1].content
        text = "".join([b["text"] if isinstance(b, dict) else str(b) for b in (last_content if isinstance(last_content, list) else [last_content])])
        
        next_player = "gm"
        match = re.search(r"\[NEXT:\s*([^\]]+)\]", text)
        if match:
            candidate = match.group(1).strip()
            next_player = candidate if candidate in self.player_ids else (self.player_ids[0] if self.player_ids else "gm")
        else:
            next_player = self.player_ids[0] if self.player_ids else "gm"
            
        return {"messages": all_new_messages, "next_player": next_player}

    def get_next_player_id(self) -> str:
        return "gm"
