import os
import json
import base64
import datetime
import re
import sqlite3
import traceback
from typing import Optional, List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI, create_context_cache
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.graph import StateGraph, START

# Try to import SqliteSaver from different possible locations
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except ImportError:
    try:
        from langgraph.checkpoint import SqliteSaver
    except ImportError:
        # Fallback to MemorySaver if Sqlite is not available
        print("WARNING: SqliteSaver not found. Persistence between restarts will not be available.")
        print("To enable persistence, please install the sqlite extension: pip install langgraph-checkpoint-sqlite")
        from langgraph.checkpoint.memory import MemorySaver as SqliteSaver

from models.game_state import GameState
from agents.gm_agent import GameMaster
from agents.player_agent import Player
from services.state_manager import StateManager

class DNDAdventure:
    """Orchestrates the game flow, graph construction, and runtime loop from a data directory."""

    def __init__(self, data_path: str, llm_model: str = "gemini-3-flash-preview"):
        self.llm_gm = ChatGoogleGenerativeAI(model="gemini-3-pro-preview", temperature=0.7)
        self.llm = ChatGoogleGenerativeAI(model=llm_model, temperature=0.7)
        
        # Persistence Setup
        db_path = os.path.join("logs", "adventure_state.db")
        os.makedirs("logs", exist_ok=True)
        
        # Determine if we are using real SQLite or just Memory fallback
        if "MemorySaver" in str(SqliteSaver):
            self.memory = SqliteSaver()
        else:
            conn = sqlite3.connect(db_path, check_same_thread=False)
            self.memory = SqliteSaver(conn)
        
        self.data_path = os.path.normpath(data_path)
        self.adventure_name = os.path.basename(self.data_path)
        
        # Load Adventure Context
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

        # Initialize Agents (Config only, state comes from Graph)
        self.players: List[Player] = []
        self.player_names = []
        pcs_dir = os.path.join(data_path, "pcs")
        if os.path.exists(pcs_dir):
            for filename in os.listdir(pcs_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(pcs_dir, filename), "r") as f:
                        pc_data = json.load(f)
                        name = pc_data["character_name"]
                        self.player_names.append(name)
                        
                        player = Player(
                            agent_id=name,
                            character_name=name,
                            llm=self.llm,
                            adventure_context=self.adventure_context,
                            physical_description=pc_data.get("physical_description") or pc_data.get("character_description"),
                            personality_description=pc_data.get("personality_description") or pc_data.get("player_description")
                        )
                        self.players.append(player)

        self.gm = GameMaster(
            self.llm_gm, 
            adventure_context=self.adventure_context, 
            player_ids=self.player_names,
            adventure_pdf_base64=self.adventure_pdf_base64
        )
        
        # Setup Caching before compiling workflow
        self._setup_context_caching()
        
        self.app = self._compile_workflow()

        # Setup Logging
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        self.full_log_path = os.path.join("logs", f"{date_str}-{self.adventure_name}-full.log")
        self.short_log_path = os.path.join("logs", f"{date_str}-{self.adventure_name}-short.log")
        self.usage_log_path = os.path.join("logs", f"{date_str}-usage.log")

    def _log_usage(self, node_name: str, metadata: Dict[str, Any]):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        usage_info = {"timestamp": timestamp, "node": node_name, "metadata": metadata}
        with open(self.usage_log_path, "a") as f:
            f.write(json.dumps(usage_info) + "\n")

    def _log(self, message: str, is_short: bool = False):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.full_log_path, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
        if is_short:
            with open(self.short_log_path, "a") as f:
                f.write(f"{message}\n")

    def _setup_context_caching(self):
        """Attempts to setup context caching for all agents."""
        print("--- SETTING UP CONTEXT CACHING ---")
        
        # We need a dummy state manager to extract tools
        initial_state = self.create_initial_state()
        manager = StateManager(initial_state)
        
        agents = [self.gm] + self.players
        
        for agent in agents:
            try:
                static_messages = agent.get_static_messages()
                tools = agent.get_tools(manager)
                
                # Minimum token count for caching is ~32k. 
                # GM PDF will hit this, players might not initially.
                # create_context_cache might raise an error if count is too low.
                
                print(f"Creating cache for {agent.name}...")
                cache_name = create_context_cache(
                    model=agent.llm,
                    messages=static_messages,
                    tools=tools,
                    ttl="3600s"
                )
                
                # Replace agent's LLM with a cached version
                cached_llm = ChatGoogleGenerativeAI(
                    model=agent.llm.model,
                    temperature=agent.llm.temperature,
                    cached_content=cache_name
                )
                agent.set_cached_llm(cached_llm)
                print(f"SUCCESS: Cache created for {agent.name}: {cache_name}")
                
            except Exception as e:
                # Standard failure if token count < 32k or other API issues
                # We just log it and proceed with standard LLM calls
                print(f"INFO: Caching skipped/failed for {agent.name}: {str(e)}")
                # Uncomment for debugging: traceback.print_exc()

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

    def create_initial_state(self) -> GameState:
        """Hydrates the initial state from JSON files."""
        state: GameState = {
            "messages": [],
            "next_player": "gm",
            "total_minutes": 8 * 60, # 08:00 AM
            "characters": {},
            "current_level": "Unknown Level",
            "current_room": "Entrance",
            "room_states": {},
            "defeated_creatures": [],
            "taken_loot": [],
            "dungeon_turn": 1
        }
        
        manager = StateManager(state)
        pcs_dir = os.path.join(self.data_path, "pcs")
        if os.path.exists(pcs_dir):
            for filename in os.listdir(pcs_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(pcs_dir, filename), "r") as f:
                        pc_data = json.load(f)
                        name = pc_data["character_name"]
                        manager.add_character(
                            name=name,
                            max_hp=pc_data.get("hp", 10),
                            ac=pc_data.get("ac", 9),
                            attack_mod=pc_data.get("attack_mod", 0),
                            damage_mod=pc_data.get("damage_mod", 0),
                            save_target=pc_data.get("save", 15)
                        )
                        state["characters"][name]["inventory"] = pc_data.get("inventory", [])
                        powers = pc_data.get("powers", [])
                        state["characters"][name]["powers"] = list(powers)
                        state["characters"][name]["daily_powers"] = list(powers)
        return state

    def start(self, thread_id: str = "game_1"):
        """Starts or resumes the adventure loop."""
        config = {"configurable": {"thread_id": thread_id}}
        
        # Check if we have an existing state
        existing_state = self.app.get_state(config)
        
        if not existing_state.values:
            # First time setup
            print(f"--- INITIALIZING NEW ADVENTURE: {thread_id} ---")
            initial_state = self.create_initial_state()
            
            # Construct party description for the initial prompt
            party_desc = "\n".join([f"- {p.character_name}: {p.physical_description}" for p in self.players])
            
            start_msg = HumanMessage(content=f"""
                The game begins! 
                Adventure Context: {self.adventure_context}
                Party: 
                {party_desc}
                GM, please describe the entrance and ask for actions.
            """)
            initial_state["messages"].append(start_msg)
            self.app.invoke(initial_state, config)
        else:
            print(f"--- RESUMING ADVENTURE: {thread_id} ---")

        skip_count = 0
        gm_turn_count = 0

        try:
            while True:
                state_obj = self.app.get_state(config)
                # Helper manager to access status
                manager = StateManager(state_obj.values)
                
                if "gm" in state_obj.next:
                    gm_turn_count += 1
                    if skip_count > 0:
                        skip_count -= 1
                        user_input = ""
                    else:
                        print(f"\n{'-'*20}\n{manager.get_party_status()}\n{'-'*20}")
                        user_input = input("OVERRIDE (Enter=Continue, Num=Skip, 'exit'): ").strip()
                        if user_input.lower() == "exit": break
                        if user_input.isdigit():
                            skip_count = int(user_input) - 1
                            user_input = ""
                    
                    if gm_turn_count % 4 == 0:
                        self._log("[PARTY_STATUS] " + manager.get_party_status(), is_short=True)
                        for name, char in state_obj.values['characters'].items():
                            inv = f"[INVENTORY] {name}: {', '.join(char['inventory']) or 'Empty'}"
                            self._log(inv, is_short=True)
                            if char['powers']:
                                pwr = f"[POWERS] {name}: {', '.join(char['powers'])}"
                                self._log(pwr, is_short=True)

                    if user_input:
                        self.app.update_state(config, {"messages": [HumanMessage(content=f"[System: {user_input}]")]})
                    
                    for event in self.app.stream(None, config, stream_mode="updates"):
                        for node, update in event.items():
                            if "messages" in update:
                                from langchain_core.messages import ToolMessage, AIMessage
                                for msg in update["messages"]:
                                    if isinstance(msg, AIMessage):
                                        self._log_usage(node, {"response_metadata": msg.response_metadata, "usage_metadata": getattr(msg, "usage_metadata", None)})

                                    text = "".join([b["text"] if isinstance(b, dict) else str(b) for b in (msg.content if isinstance(msg.content, list) else [msg.content])])
                                    log_entry = f"[{node.upper()}] {text}"
                                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                                        log_entry += f" (Tools: {msg.tool_calls})"
                                    self._log(log_entry)
                                    
                                    if not isinstance(msg, ToolMessage) and not (isinstance(msg, AIMessage) and msg.tool_calls and not text.strip()):
                                        clean_text = re.sub(r"\[NEXT:\s*([^\]]+)\]", "", text).strip()
                                        if clean_text:
                                            output_line = f"[{node.upper()}] {clean_text}"
                                            print(f"\n{output_line}")
                                            self._log(output_line, is_short=True)
                                    elif isinstance(msg, AIMessage) and msg.tool_calls:
                                        for tc in msg.tool_calls:
                                            self._log(f"[{node.upper()}] (TOOL) {tc['name']}({tc['args']})", is_short=True)
                                    elif isinstance(msg, ToolMessage):
                                        self._log(f"[SYSTEM] {text}", is_short=True)
                else:
                    self.app.invoke(None, config)
        except KeyboardInterrupt:
            print("\nPaused.")
