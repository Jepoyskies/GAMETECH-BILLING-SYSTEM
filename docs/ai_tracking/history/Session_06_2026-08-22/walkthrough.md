# Live Monitoring UI Redesign

The Live Monitoring dashboard has been completely stripped of its custom "Glassmorphism" styling and fully ported to the company's native design system, allowing it to seamlessly adapt to the global Light/Dark mode settings.

## What changed?
1. **Design System Port**: The entire page was rewritten to use standard `.dashboard-card` elements instead of custom glass panels. This matches the exact aesthetic of your main administrative Dashboard.
2. **Light/Dark Mode Fix**: All hardcoded colors (like `#020617` backgrounds and `var(--neon-purple)` texts) have been stripped from both the HTML and the Javascript polling engine. They were replaced with Bootstrap's native `text-body`, `text-muted`, and `bg-primary-subtle` classes, which dynamically flip colors when you toggle the theme.
3. **Renaming**: The page title has been updated from "Command Center" to "Live Monitoring".

## Verification
You can verify the changes by:
- Navigating to the **Live Monitoring** dashboard.
- Clicking the moon/sun icon in the top right to toggle between Light Mode and Dark Mode. You will see the entire dashboard—including all the Javascript-generated active alerts and offline customers—instantly invert their colors without any unreadable text!
