# Add Router Uplink Live Monitoring

This plan outlines the addition of a "Router Uplink Health" monitor to the Live Monitoring page, allowing you to instantly see if the main MikroTik router has lost its internet connection or is experiencing high latency (unstable).

## Proposed Changes

### 1. Backend Data Source
We will modify the AJAX endpoint used by the Live Monitoring page (`api_live_monitoring_data` in `billing/views.py`).
- It will now send a single `ping` request to `8.8.8.8` through the MikroTik API every time the dashboard polls for traffic data.
- If the ping fails (100% packet loss) or returns "no route to host", it will report **Offline**.
- If the ping returns but is higher than 150ms, it will report **Unstable**.
- Otherwise, it reports **Online**.
- The API response format will be updated from a flat list of users to a structured JSON object containing both `users` and `routers`.

### 2. Frontend Dashboard Updates
We will modify `billing/templates/billing/live_monitoring.html`.
- Add a new "Uplink Status" widget at the very top of the page (near the Total Bandwidth).
- Update the Javascript fetching logic to parse the new JSON structure and update the Uplink Status widget in real-time.
- If the router goes offline, the widget will glow red and show "Offline (Timeout)".
- If it is unstable, it will show orange.

## User Review Required
- Is pinging `8.8.8.8` acceptable for determining the internet health of the router?
- Do you want a dedicated button on this dashboard to quickly send the "System Down" broadcast SMS to all users if the router is offline, or is just displaying the status enough for now?

Please approve this plan to begin implementation.
