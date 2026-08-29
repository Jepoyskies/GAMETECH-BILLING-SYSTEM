# Sync Manager Redesign Tasks

- `[x]` Update `network_manager/sync_services.py` to add advanced suspicious user detection logic.
- `[x]` Update `network_manager/views.py` `sync_manager` to split orphans into `clean_orphans` and `suspicious_orphans`.
- `[x]` Update `network_manager/templates/network_manager/sync_manager.html` to:
  - `[x]` Rename "Synced Users" to "Active Users".
  - `[x]` Show "Mikrotik Router Users" (Clean Orphans).
  - `[x]` Show "Unknown/Suspicious Users" (Suspicious Orphans) with bold red/warning styling.
  - `[x]` Ensure "Missing on Router" stays with consistent UI.
  - `[x]` Enhance overall UI with premium cards and modern styling matching the theme.
- `[ ]` Test rendering to ensure no 500 errors.
- `[ ]` Commit and deploy to live server.
