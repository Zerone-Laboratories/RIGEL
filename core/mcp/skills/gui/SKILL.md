# Skill: gui

Interactive GUI components for confirmations/inputs.

## Tools

- display_interactive_components_for_user
- quickshell_gui
- kill_gui_window

## Workflows

### Workflow: Ask user to confirm an action

1. Call `display_interactive_components_for_user("confirm", {...})`.
2. Use the returned selection to proceed or abort.

### Workflow: Collect a sensitive value (password/key)

1. Use `display_interactive_components_for_user("input", {"echo_mode": "TextField.Password", ...})`.
2. Use the returned value in the next tool call.
