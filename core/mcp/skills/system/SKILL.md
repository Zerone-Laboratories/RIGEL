# Skill: system

System introspection and safe shell execution.

## Tools

- system_specs
- run_bash_command
- show_available_commands

## Workflows

### Workflow: Quick system snapshot

1. Call `system_specs`.
2. Use the returned information to decide next steps (OS, CPU, memory, etc.).

### Workflow: Run a shell command

1. Prefer narrow, read-only commands.
2. Call `run_bash_command(command=...)`.
3. If output is large, refine the command (e.g., add `head`, `tail`, or filters).
