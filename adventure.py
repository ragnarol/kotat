import os
import json
import base64
import datetime
import re
from typing import Optional, List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.graph import StateGraph, START
from langgraph.checkpoint.memory import MemorySaver

from models.game_state import GameState
from agents.gm_agent import GameMaster
from agents.player_agent import Player
from services.state_manager import StateManager

class DNDAdventure:
    """Orchestrates the game flow, graph construction, and runtime loop from a data directory."""

    def __init__(self, data_path: str, llm_model: str = "gemini-3-flash-preview"):
        self.llm_gm = ChatGoogleGenerativeAI(model="gemini-3-pro-preview", temperature=0.7)
        self.llm = ChatGoogleGenerativeAI(model=llm_model, temperature=0.7)
        self.memory = MemorySaver()
        self.data_path = os.path.normpath(data_path)
        self.adventure_name = os.path.basename(self.data_path)
        self.state_manager = StateManager()
        
        adventure_file = os.path.join(data_path, "adventure.json")
        with open(adventure_file, "r") as f:
            adventure_data = json.load(f)
            self.adventure_context = adventure_data.get("adventure_context", "")
            self.adventure_pdf_name = adventure_data.get("adventure_pdf")

        self.adventure_pdf_base64 = None
        if self.adventure_pdf_name:
            pdf_path = os.path.join(data_path, self.adventure_pdf_name)
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as pdf_file:
                    self.adventure_pdf_base64 = base64.b64encode(pdf_file.read()).decode('utf-8')

        self.players: List[Player] = []
        pcs_dir = os.path.join(data_path, "pcs")
        if os.path.exists(pcs_dir):
            for filename in os.listdir(pcs_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(pcs_dir, filename), "r") as f:
                        pc_data = json.load(f)
                        name = pc_data["character_name"]
                        
                        # Hydrate State Manager
                        self.state_manager.add_character(
                            name=name,
                            max_hp=pc_data.get("hp", 10),
                            ac=pc_data.get("ac", 9),
                            attack_mod=pc_data.get("attack_mod", 0),
                            save_target=pc_data.get("save", 15)
                        )
                        self.state_manager.characters[name].inventory = pc_data.get("inventory", [])

                        player = Player(
                            agent_id=name,
                            character_name=name,
                            llm=self.llm,
                            state_manager=self.state_manager,
                            adventure_context=self.adventure_context,
                            character_description=pc_data.get("character_description"),
                            player_description=pc_data.get("player_description")
                        )
                        self.players.append(player)

        self.gm = GameMaster(
            self.llm_gm, 
            state_manager=self.state_manager,
            adventure_context=self.adventure_context, 
            player_ids=[p.character_name for p in self.players],
            adventure_pdf_base64=self.adventure_pdf_base64
        )
        
        self.app = self._compile_workflow()

        # Setup Logging
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        self.full_log_path = os.path.join("logs", f"{date_str}-{self.adventure_name}-full.log")
        self.short_log_path = os.path.join("logs", f"{date_str}-{self.adventure_name}-short.log")
        self.usage_log_path = os.path.join("logs", f"{date_str}-usage.log")

    def _log_usage(self, node_name: str, metadata: Dict[str, Any]):
        """Logs LLM usage metadata (tokens, cache, etc.)."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        usage_info = {
            "timestamp": timestamp,
            "node": node_name,
            "metadata": metadata
        }
        with open(self.usage_log_path, "a") as f:
            f.write(json.dumps(usage_info) + "\n")

    def _log(self, message: str, is_short: bool = False):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.full_log_path, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
        if is_short:
            with open(self.short_log_path, "a") as f:
                f.write(f"{message}\n")

    def _compile_workflow(self):
        workflow = StateGraph(GameState)
        workflow.add_node("gm", self.gm.run)
        mapping = {"gm": "gm"}
        for player in self.players:
            workflow.add_node(player.character_name, player.run)
            mapping[player.character_name] = player.character_name
            workflow.add_edge(player.character_name, "gm")

        workflow.add_edge(START, "gm")
        workflow.add_conditional_edges("gm", lambda state: state["next_player"], mapping)
        return workflow.compile(checkpointer=self.memory, interrupt_before=["gm"])

    def start(self, initial_state: GameState, thread_id: str = "game_1"):
        config = {"configurable": {"thread_id": thread_id}}
        skip_count = 0
        print("--- ADVENTURE START ---")
        self.app.invoke(initial_state, config)

        try:
            while True:
                state = self.app.get_state(config)
                if "gm" in state.next:
                    if skip_count > 0:
                        skip_count -= 1
                        user_input = ""
                    else:
                        print(f"\n{'-'*20}\n{self.state_manager.get_party_status()}\n{'-'*20}")
                        user_input = input("OVERRIDE (Enter=Continue, Num=Skip, 'exit'): ").strip()
                        if user_input.lower() == "exit": break
                        if user_input.isdigit():
                            skip_count = int(user_input) - 1
                            user_input = ""
                    
                    if user_input:
                        self.app.update_state(config, {"messages": [HumanMessage(content=f"[System: {user_input}]")]})
                    
                    for event in self.app.stream(None, config, stream_mode="updates"):
                        for node, update in event.items():
                            if "messages" in update:
                                from langchain_core.messages import ToolMessage, AIMessage
                                for msg in update["messages"]:
                                    # Log usage if metadata is present
                                    if isinstance(msg, AIMessage):
                                        usage_data = {
                                            "response_metadata": msg.response_metadata,
                                            "usage_metadata": getattr(msg, "usage_metadata", None)
                                        }
                                        self._log_usage(node, usage_data)

                                    text = "".join([b["text"] if isinstance(b, dict) else str(b) for b in (msg.content if isinstance(msg.content, list) else [msg.content])])
                                    log_entry = f"[{node.upper()}] {text}"
                                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                                        log_entry += f" (Tools: {msg.tool_calls})"
                                    self._log(log_entry)
                                    
                                    if not isinstance(msg, ToolMessage) and not (isinstance(msg, AIMessage) and msg.tool_calls and not text.strip()):
                                        # Clean up [NEXT: ...] for the short log and console
                                        clean_text = re.sub(r"\[NEXT:\s*([^\]]+)\]", "", text).strip()
                                        if clean_text:
                                            output_line = f"[{node.upper()}] {clean_text}"
                                            print(f"\n{output_line}")
                                            self._log(output_line, is_short=True)
                                    elif isinstance(msg, AIMessage) and msg.tool_calls:
                                        # If it's a tool call, log it in the short log
                                        for tc in msg.tool_calls:
                                            tool_line = f"[{node.upper()}] (TOOL) {tc['name']}({tc['args']})"
                                            self._log(tool_line, is_short=True)
                                    elif isinstance(msg, ToolMessage):
                                        # Log tool results in the short log too
                                        result_line = f"[SYSTEM] {text}"
                                        self._log(result_line, is_short=True)
                else:
                    self.app.invoke(None, config)
        except KeyboardInterrupt:
            print("\nPaused.")
