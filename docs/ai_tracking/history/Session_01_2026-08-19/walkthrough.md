# Router Uplink Live Monitoring Implemented

I have successfully added the Router Uplink Monitoring feature to your Live Monitoring dashboard!

## What was implemented
1. **API Update**: Every time the dashboard fetches live traffic data, the Django backend now sends an internal `/ping` command through the MikroTik RouterOS API to `8.8.8.8`. 
2. **Health Logic**: 
   - If the ping fails or times out, it reports the router as **Offline**.
   - If the ping succeeds but the average latency is greater than 150ms, it reports **Unstable**.
   - Otherwise, it reports **Online**.
3. **UI Widget**: A new purple widget titled **Router Uplink** has been added to the top left of the summary grid on the Live Monitoring page.

## Real-time Dynamic Feedback
The new widget scales and changes colors dynamically without refreshing the page:
- **🟢 Online**: Normal purple gradient, shows current ping (e.g. `Ping: 12ms`).
- **🟡 Unstable**: Turns glowing Orange to warn you of latency spikes or dropped packets.
- **🔴 Offline**: Turns bright Red and says `Timeout` if the main router loses internet access.

## How to test it
Go to the **Live Monitoring** page in your sidebar. You will see the new **Router Uplink** box at the top. If you unplug the main router from your ISP modem (or disconnect your repeater), you will see it turn Red and report "Offline" within seconds!
