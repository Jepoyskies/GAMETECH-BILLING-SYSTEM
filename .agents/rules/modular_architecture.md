---
name: Modular Architecture and Clean Code Guidelines
description: Guidelines for AI agents and human developers on how to maintain the modular structure of the GAMETECH BILLING SYSTEM.
---

# Modular Architecture & Code Organization Guidelines

To keep the GAMETECH-BILLING-SYSTEM maintainable, efficient, and AI-friendly, all developers (and AI assistants) MUST adhere to the following file size and modularity rules. 

## 1. Strict File Size Limits
- **HTML Templates**: No single HTML file should exceed **400-500 lines**.
- **Python Views/Models**: No single Python file should exceed **400 lines**.
- **CSS/JS Assets**: Avoid monolithic files. Break down styles into components.

## 2. Managing Large HTML Templates (The Orchestrator Pattern)
If a page requires a lot of code (like `dashboard.html`), it MUST be split using the **Orchestrator Pattern**:
- The main template file acts ONLY as an **orchestrator**. It should consist primarily of `{% include %}` statements.
- All actual UI components (modals, charts, specific widget cards, CSS, JS) must be separated into partial files inside a subdirectory named after the orchestrator template (e.g., `billing/templates/billing/dashboard/`).
- Prefix partial filenames with an underscore (e.g., `_kpi_cards.html`, `_scripts.html`).

**AI INSTRUCTION**: If a user asks you to add a new feature, modal, or widget to the dashboard or any other major page:
1. **DO NOT** add the code directly into the main `dashboard.html` orchestrator unless you are just adding a new `{% include %}` tag.
2. Locate the appropriate partial file (e.g., `_modal_recent_logins.html`) and add it there, OR create a brand new partial file (e.g., `_modal_new_feature.html`) and include it in the orchestrator.

## 3. Python Views and Services
- Do not stuff all business logic into `views.py`.
- If a view module (e.g., `billing/views/customers.py`) becomes too large, split it further by separating concerns (e.g., `billing/views/customers_api.py`, `billing/views/customers_rendering.py`) or by moving heavy business logic into a `services.py` layer.

## 4. CSS and JS Modularity
- Instead of adding styles to a monolithic `theme.css`, create modular CSS files if the styling is specific to a feature.
- For template-specific scripts, use a partial (e.g., `_scripts.html`) included at the bottom of the orchestrator template.

By following these rules, we ensure that the system remains fast to debug, saves AI context window credits, and allows multiple team members to work on different components simultaneously without causing massive git merge conflicts.
