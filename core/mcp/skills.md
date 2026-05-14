# RIGEL Tools Skills (Legacy Index)

RIGEL now uses a **modular skills architecture**.

Each skill is a folder under:

- `core/mcp/skills/<skill_name>/SKILL.md`

Those `SKILL.md` files define:

- Which tools belong to the skill
- How the agent should use them (workflows/playbooks)

This file is kept as a **legacy fallback** only.
If `core/mcp/skills/` exists, the tool server will load skills from the modular folders instead of this file.

## Modules

- `mobile_aci` → `core/mcp/skills/mobile_aci/SKILL.md`
- `system` → `core/mcp/skills/system/SKILL.md`
- `network` → `core/mcp/skills/network/SKILL.md`
- `gui` → `core/mcp/skills/gui/SKILL.md`
