# Migrate Live Monitoring to Native Company Design

The current "Glassmorphism" design forces a permanent dark theme which breaks the company's global Light/Dark mode toggle, and visually conflicts with the rest of the application (like the Dashboard).

I will completely strip out the custom styling and port the Live Monitoring dashboard over to the company's native design system while keeping the highly-efficient CSS Grid layout you liked.

## Proposed Changes

### CSS & Layout Overhaul
- **Remove Hardcoded Theme**: Delete the custom `<style>` block forcing the `#020617` background and white text.
- **Convert Cards**: Replace all `.glass-card` elements with the company's native `.dashboard-card` class (used in `dashboard.html`).
- **Standardize Typography**: Replace custom fonts (`Space Grotesk`) and hardcoded hex colors (`#94a3b8`, `#fcd34d`, etc.) with native Bootstrap utility classes (`text-muted`, `text-warning`, `text-body`). This ensures text automatically inverts correctly when switching between Light and Dark mode.
- **Update Title**: Change the main header from "Command Center" to "Live Monitoring".

### JavaScript Updates
- **Remove Inline Neon Styles**: Clean up the Javascript template literals (for Network Alerts and Add-on Requests) to remove all `var(--neon-...)` inline borders and backgrounds.
- **Use Bootstrap Contextual Colors**: Use standard `bg-warning-subtle`, `text-warning`, `bg-danger-subtle` etc., in the Javascript loops so they adapt seamlessly to the global theme toggle.

## Open Questions

> [!TIP]
> The current layout uses a highly condensed "Grid" system that fits all 6 KPI cards horizontally on large screens. Do you want to keep this dense grid layout, or would you prefer I revert the grid to a standard Bootstrap Row/Column layout (like the Dashboard uses)? 

## Verification Plan
1. Switch the application to **Light Mode** and verify no text is unreadable (white-on-white).
2. Switch the application to **Dark Mode** and verify the `.dashboard-card` styles apply correctly.
3. Verify the Javascript polling continues to render rows with the new Bootstrap styles.
