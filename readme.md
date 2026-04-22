# Knights of the AI Table (KOTAT)

Knights of the AI Table is a specialized framework for running automated, AI-driven tabletop RPG sessions, specifically tailored for the "Red Box" D&D era. It uses advanced LLMs to simulate both a Game Master (GM) and a party of Player Characters (PCs) in a persistent, reactive world.

## 🏗 Architecture

The project follows a modular, object-oriented design with "one class per file" sensibilities:

-   **`agents/`**: Contains the core logic for the different actors.
    -   `BaseAgent`: Abstract base for all agents.
    -   `GameMaster`: Responsible for narration, action resolution, and tool usage.
    -   `Player`: Simulates character behavior based on physical and personality descriptions.
-   **`models/`**: Defines the data structures.
    -   `GameState`: The single source of truth, managed and persisted by LangGraph.
-   **`services/`**: Supporting services.
    -   `StateManager`: A helper that operates on the `GameState` to manage time, HP, items, effects, and room states.
-   **`adventure.py`**: The orchestrator. It builds the LangGraph workflow, handles the main loop, and manages persistence.
-   **`redbox_tools.py`**: Custom tools (dice rolling, time advancement, combat, etc.) that the GM can call.

## 🎨 Design Decisions

-   **LangGraph Orchestration**: The game flow is a state machine where the GM nominates the next player to act. This allows for dynamic, non-linear turn orders.
-   **Full Persistence**: Using SQLite checkpointers, the entire game state (including message history and character sheets) is saved automatically. You can stop and resume your adventure at any time.
-   **Multimodal Context**: The GM can "read" actual rulebooks or adventure modules in PDF format, which are injected into its context as media objects.
-   **Separation of Concerns**: PCs describe *intent* and *actions* (roleplay), while the GM handles all *mechanics* (rolling dice, checking AC, applying damage) using specialized tools.
-   **Dual-Layer Logging**:
    -   **Full Log**: Technical JSON-heavy log of every internal event.
    -   **Short Log**: A clean, character-labeled narrative of the story.
    -   **Markdown Export**: A script transforms logs into beautiful, readable adventure journals.

## 🛠 Configuration

Adventures are loaded from folders. A valid adventure folder (like the included `stonehell`) must contain:

1.  **`adventure.json`**:
    ```json
    {
      "adventure_context": "Overview of the setting.",
      "adventure_pdf": "filename.pdf" (Optional)
    }
    ```
2.  **`gm.json`**: Configuration for the Game Master.
3.  **`pcs/` folder**: A collection of JSON files, one per character:
    ```json
    {
      "character_name": "Korg",
      "physical_description": "...",
      "personality_description": "...",
      "hp": 12, "ac": 2, "attack_mod": 1, "damage_mod": 1, "save": 14,
      "inventory": ["Longsword", "Torch"],
      "powers": ["Cure Light Wounds"]
    }
    ```

## 🚀 How to Run

### Prerequisites
- Python 3.10+
- `GOOGLE_API_KEY` set in your environment.
- Dependencies: `langchain-google-genai`, `langgraph`, `langgraph-checkpoint-sqlite` (optional but recommended for persistence).

### Starting an Adventure
Run the main script and provide the path to your adventure folder:
```bash
python3 main.py stonehell
```

### During the Game
-   **Enter**: Advance to the next turn.
-   **Number (e.g., `5`)**: Run X turns automatically without stopping for human intervention.
-   **Type message**: Inject a "Voice of God" system note to guide the AI or correct the state.
-   **`exit`**: Save and quit.

### Generating Journals
After playing, transform your short log into a formatted Markdown journal:
```bash
python3 format_log.py
```
The result will be saved in the `logs/` folder.

## 📊 Usage Monitoring
Every session generates a `YYYYMMDD-usage.log` containing detailed metadata about token consumption and cache performance for each LLM call.
