# Agent Orchestrators

Entry point agents that provide UI and routing for CI/CD pipeline generation.

## Agents in This Folder

### netcore-orchestrator
**Purpose**: Unified UI for .NET Core CI/CD pipeline selection

**What it does**:
- Displays interface with Git repository URL input
- Shows CI and CD pipeline options
- Routes user selection to appropriate worker agent
- Reports agent execution status

**How to run**:
```bash
cd netcore-orchestrator
uv sync
cp .env.example .env
# Edit .env with AGENT_MODEL and ANTHROPIC_API_KEY
uv run agent
```

**System Prompt**: `src/agent/prompts/system.md` (31 lines)
- Defines orchestrator role
- Explains UI responsibilities
- Key constraints and principles

**Skills**: `src/agent/skills/` (1 file)
- UI presentation and user interaction

**Tools**: `src/agent/tools/tools.py` (4 implementations)
- `DisplayOrchestratorUI()` - Show interface
- `RunCIAgent()` - Trigger CI agent
- `RunCDAgent()` - Trigger CD agent
- `GetAgentStatus()` - Track execution

---

## Adding New Orchestrators

To add a new orchestrator for a different technology stack:

```bash
cp -r /Users/komalipyla/Desktop/agent/agent-starter netcore-orchestrator-v2
```

Then customize:
1. `pyproject.toml` - Update agent name
2. `src/agent/prompts/system.md` - Define new orchestrator role
3. `src/agent/skills/example.md` - Define capabilities
4. `src/agent/tools/tools.py` - Implement tools for new tech stack

---

## Architecture

All orchestrators follow this pattern:
1. Accept user input (repository URL, options)
2. Display available worker agent options
3. Route to selected worker agent
4. Report back execution status

---

**See also**:
- [Main README](../README.md)
- [QUICK_START.md](../QUICK_START.md)
