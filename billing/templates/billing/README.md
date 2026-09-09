# Django Templates (Orchestrator Pattern)

This directory follows the **Orchestrator Pattern** to ensure templates remain modular, clean, and AI-friendly (specifically optimized for Google Antigravity).

## The Rules
1. **No Monoliths**: Main template files (e.g., `dashboard.html`, `customer_list.html`) act ONLY as orchestrators. They should be under 50 lines.
2. **Partials Directory**: Every orchestrator must have a corresponding subdirectory (e.g., `dashboard/`) containing its partials.
3. **Dedicated Styles/Scripts**: CSS and JS must be extracted into `_styles.html` and `_scripts.html` inside the partials directory.
4. **Modals**: Extracted into individual `_modal_<name>.html` files.

*Adhere to these rules to maintain fast debugging and low token usage.*
