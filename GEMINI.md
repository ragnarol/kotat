# Development Preferences

## Architectural Style: Object-Oriented
- Always prefer a clean, object-oriented approach over procedural or "spaghetti" code.
- Use abstract base classes (ABCs) for defining interfaces and common behavior.
- Use type hinting extensively to improve readability and catch errors.

## File Structure: "One Class Per File"
- Follow the C# convention of keeping a single primary class per file.
- Organize files into logical directories (e.g., `models/`, `agents/`, `services/`).
- Ensure `__init__.py` files are updated or that absolute imports are used to maintain a clean namespace.

## Engineering Constraints
- **No Automated Installations:** Never run `pip install` or other package managers. The user manages the environment via a devcontainer. If a dependency is missing, report it and ask for guidance.
- **Python with C# Sensibilities:** While writing Python, apply C# patterns (Dependency Injection, Strategy Pattern, etc.) where appropriate to keep the codebase modular and testable.
