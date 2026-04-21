import os
import json
import base64
import datetime
from typing import Optional, List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.graph import StateGraph, START
from langgraph.checkpoint.memory import MemorySaver

from models.game_state import GameState
from agents.gm_agent import GameMaster
from agents.player_agent import Player

class DNDAdventure:
    """Orchestrates the game flow, graph construction, and runtime loop from a data directory."""

    def __init__(self, data_path: str, llm_model: str = "gemini-3-flash-preview"):
        self.llm_gm = ChatGoogleGenerativeAI(model="gemini-3-pro-preview", temperature=0.7)
        self.llm = ChatGoogleGenerativeAI(model=llm_model, temperature=0.7)
        self.memory = MemorySaver()
        self.data_path = os.path.normpath(data_path)
        self.adventure_name = os.path.basename(self.data_path)
        
        # Load Adventure Context
        adventure_file = os.path.join(data_path, "adventure.json")
        with open(adventure_file, "r") as f:
            adventure_data = json.load(f)
            self.adventure_context = adventure_data.get("adventure_context", "")
            self.adventure_pdf_name = adventure_data.get("adventure_pdf")

        # Encode PDF if it exists
        self.adventure_pdf_base64 = None
        if self.adventure_pdf_name:
            pdf_path = os.path.join(data_path, self.adventure_pdf_name)
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as pdf_file:
                    self.adventure_pdf_base64 = base64.b64encode(pdf_file.read()).decode('utf-8')

        # Load Players
        self.players: List[Player] = []
        pcs_dir = os.path.join(data_path, "pcs")
        if os.path.exists(pcs_dir):
            for filename in os.listdir(pcs_dir):
                if filename.endswith(".json"):
                    with open(os.path.join(pcs_dir, filename), "r") as f:
                        pc_data = json.load(f)
                        player = Player(
                            agent_id=pc_data["character_name"],
                            character_name=pc_data["character_name"],
                            llm=self.llm,
                            adventure_context=self.adventure_context,
                            character_description=pc_data.get("character_description"),
                            player_description=pc_data.get("player_description")
                        )
                        self.players.append(player)

        # Initialize GM with knowledge of players and PDF
        self.gm = GameMaster(
            self.llm_gm, 
            adventure_context=self.adventure_context, 
            player_ids=[p.character_name for p in self.players],
            adventure_pdf_base64=self.adventure_pdf_base64
        )
        
        # Build Workflow
        self.app = self._compile_workflow()
        
        # Setup Logging
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        self.full_log_path = os.path.join("logs", f"{date_str}-{self.adventure_name}-full.log")
        self.short_log_path = os.path.join("logs", f"{date_str}-{self.adventure_name}-short.log")

    def _log(self, message: str, is_short: bool = False):
        """Logs a message to the appropriate files."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.full_log_path, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
        
        if is_short:
            with open(self.short_log_path, "a") as f:
                f.write(f"{message}\n")

    def _compile_workflow(self):
        workflow = StateGraph(GameState)
        
        # Add nodes using the agent's run methods
        workflow.add_node("gm", self.gm.run)
        
        player_nodes = {}
        for player in self.players:
            node_id = player.character_name
            workflow.add_node(node_id, player.run)
            player_nodes[node_id] = node_id

        # Define Edges
        workflow.add_edge(START, "gm")
        
        mapping = {pid: pid for pid in player_nodes}
        mapping["gm"] = "gm"
        
        workflow.add_conditional_edges(
            "gm", 
            lambda state: state["next_player"], 
            mapping
        )
        
        for node_id in player_nodes:
            workflow.add_edge(node_id, "gm")

        return workflow.compile(checkpointer=self.memory, interrupt_before=["gm"])

    def start(self, initial_state: GameState, thread_id: str = "game_1"):
        """Starts the adventure loop."""
        config = {"configurable": {"thread_id": thread_id}}
        skip_intervention_count = 0
        
        print("--- ADVENTURE START ---")
        self._log("--- ADVENTURE START ---")
        self.app.invoke(initial_state, config)

        try:
            while True:
                state = self.app.get_state(config)
                
                if "gm" in state.next:
                    user_input = ""
                    if skip_intervention_count > 0:
                        skip_intervention_count -= 1
                    else:
                        print("\n" + "="*40)
                        user_input = input("HUMAN OVERRIDE (Enter to continue, number to skip X turns, 'exit' to quit): ").strip()
                        
                        if user_input.lower() == "exit":
                            break
                        
                        if user_input.isdigit():
                            skip_intervention_count = int(user_input) - 1
                            user_input = ""
                    
                    if user_input:
                        note = f"[System Note: {user_input}]"
                        self.app.update_state(config, {"messages": [HumanMessage(content=note)]})
                        self._log(f"USER INTERVENTION: {user_input}")
                    
                    for event in self.app.stream(None, config, stream_mode="updates"):
                        for node_name, node_update in event.items():
                            if "messages" in node_update:
                                content = node_update["messages"][-1].content
                                # Handle list content for logging
                                if isinstance(content, list):
                                    text = "".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in content])
                                else:
                                    text = str(content)
                                
                                print(f"\n[{node_name.upper()}]\n{text}")
                                self._log(f"[{node_name.upper()}] {text}", is_short=True)
                else:
                    self.app.invoke(None, config)
        except KeyboardInterrupt:
            print("\nAdventure paused.")
