from typing import Optional, List, Dict, Any
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, ToolMessage
from agents.base_agent import BaseAgent
from models.game_state import GameState
from redbox_tools import roll_dice, create_redbox_tools
from services.state_manager import StateManager

class GameMaster(BaseAgent):
    """The Game Master agent responsible for world narration and action resolution."""
    
    def __init__(self, llm: ChatGoogleGenerativeAI, 
                 adventure_context: Optional[str] = None, 
                 player_ids: List[str] = None, 
                 adventure_pdf_base64: Optional[str] = None):
        super().__init__("GameMaster", llm)
        self.adventure_context = adventure_context or ""
        self.player_ids = player_ids or []
        self.adventure_pdf_base64 = adventure_pdf_base64

    def get_static_messages(self) -> List[BaseMessage]:
        """Returns the static instructions and adventure PDF for caching."""
        content = f"""You are the Game Master for a Red Box D&D game. 
        Your job is to describe the results of player actions and narrate the world. 
        Check for traps, rolls, or monster reactions as needed.
        
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
            
        messages = [SystemMessage(content=content)]
        
        if self.adventure_pdf_base64:
            pdf_context = HumanMessage(
                content=[
                    {"type": "text", "text": "Reference rulebook/adventure PDF for mechanics and setting:"},
                    {"type": "media", "mime_type": "application/pdf", "data": self.adventure_pdf_base64}
                ]
            )
            messages.append(pdf_context)
            
        return messages

    def get_tools(self, state_manager: StateManager) -> List[Any]:
        """Returns the set of tools the GM can use."""
        return [roll_dice] + create_redbox_tools(state_manager)

    def _get_system_message(self, state_manager: StateManager) -> SystemMessage:
        """Returns the dynamic state information."""
        content = f"""Current game time: {state_manager.get_time_string()}
        Party Status: {state_manager.get_party_status()}"""
        return SystemMessage(content=content)

    def _preprocess_history(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        return list(messages)

    def _get_poke_message(self) -> HumanMessage:
        return HumanMessage(content="[GM: Resolve actions, describe the scene, nominate next player.]")

    def run(self, state: GameState) -> Dict[str, Any]:
        state_manager = StateManager(state)
        tools = self.get_tools(state_manager)
        
        # If cached, tools are already bound. Otherwise, bind them now.
        llm_runnable = self.llm if self.is_cached else self.llm.bind_tools(tools)

        # Automatically advance time by 1 minute per turn
        expiration_events = state_manager.advance_time(1)
        
        history = self._preprocess_history(state["messages"])
        
        # If any effects expired, inform the LLM by prepending a system note to the history
        if expiration_events:
            event_note = "[System Note: " + " ".join(expiration_events) + "]"
            history.append(HumanMessage(content=event_note))

        system_msg = self._get_system_message(state_manager)
        
        # If cached, we cannot use SystemMessage in the dynamic call
        dynamic_context = [system_msg] if not self.is_cached else [HumanMessage(content=f"[STATUS UPDATE]\n{system_msg.content}")]

        prompt = [*dynamic_context, *history, self._get_poke_message()]
        
        all_new_messages = []
        while True:
            response = llm_runnable.invoke(prompt)
            response.name = self.name
            all_new_messages.append(response)
            if not response.tool_calls:
                break
                
            prompt.append(response)
            for tool_call in response.tool_calls:
                tool_to_use = next((t for t in tools if t.name == tool_call["name"]), None)
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
