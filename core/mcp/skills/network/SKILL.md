# Skill: network

Network status and Wi‑Fi management.

## Tools

- network_status
- toggle_wifi
- get_wifi_networks
- connect_wifi

## Workflows

### Workflow: Diagnose connectivity

1. Call `network_status`.
2. If Wi‑Fi is off, call `toggle_wifi(enabled=true)`.
3. Call `get_wifi_networks` to confirm visibility.

### Workflow: Connect to Wi‑Fi

1. Call `get_wifi_networks`.
2. Choose SSID.
3. Call `connect_wifi(ssid=..., password=...)`.
4. Validate with `network_status`.
