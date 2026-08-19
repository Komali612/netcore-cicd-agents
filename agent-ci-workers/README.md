# Agent CI Workers

CI pipeline generation agents for different technology stacks.

## Agents in This Folder

### netcore-ci-agent
**Purpose**: Generate GitHub Actions CI pipelines for .NET Core 6/7/8 applications

**What it does**:
1. **Discover** - Analyzes repository structure and framework
2. **Generate** - Authors GitHub Actions workflow with all required stages
3. **Validate** - Lints and validates workflow (up to 3 attempts)
4. **Deploy** - Opens PR for human review

**Workflow Stages**:
- Build (using discovered .NET CLI/MSBuild/NuGet)
- Unit Tests (with SonarQube coverage - required)
- SAST (Fortify)
- SCA (Sonatype)
- DAST (Fortify WebInspect - configurable)
- Docker Image Build & Scan (Wiz)
- SBOM Generation
- Nexus Artifact Storage
- Helm Chart Update
- Dynatrace & Splunk Monitoring

**How to run**:
```bash
cd netcore-ci-agent
uv sync
cp .env.example .env
# Edit .env with AGENT_MODEL and ANTHROPIC_API_KEY
uv run agent
```

**System Prompt**: `src/agent/prompts/system.md` (51 lines)
- Defines complete CI workflow
- Explains discovery, generation, validation, deployment phases
- Constraints: 3-attempt limit, human review, no overwrite

**Skills**: `src/agent/skills/` (4 files)
- Discover (repository analysis)
- Generate (workflow creation)
- Validate (YAML linting and testing)
- Deploy (PR creation)

**Tools**: `src/agent/tools/tools.py` (4 implementations)
- `DiscoverProject()` - Analyze .NET Core repo
- `GenerateGitHubActionsWorkflow()` - Create workflow YAML
- `ValidateWorkflow()` - Validate syntax and structure
- `CreatePullRequest()` - Open PR for review

---

## Adding New CI Workers

To add a CI worker for a new technology (e.g., Java, Python, Go):

```bash
cp -r /Users/komalipyla/Desktop/agent/agent-starter java-ci-agent
```

Then customize:
1. `pyproject.toml` - Update agent name, add tech-specific deps
2. `src/agent/prompts/system.md` - Define Java CI workflow
3. `src/agent/skills/*.md` - Define Java-specific capabilities
4. `src/agent/tools/tools.py` - Implement Java project discovery and build

Example structure for Java:
```
java-ci-agent/
├── src/agent/prompts/system.md          (Maven/Gradle build discovery)
├── src/agent/skills/
│   ├── discover.md                      (POM.xml analysis)
│   ├── generate-pipeline.md             (Maven/Gradle workflows)
│   ├── validate-pipeline.md
│   └── deploy-pipeline.md
└── src/agent/tools/tools.py             (Maven/Gradle tools)
```

---

## CI Worker Pattern

All CI workers follow this pattern:

```
1. DISCOVER
   ├─ Clone repository
   ├─ Detect project structure
   ├─ Identify build tool/framework
   ├─ Check for existing CI pipeline
   └─ Extract SDK/runtime requirements

2. GENERATE
   ├─ Create pipeline configuration
   ├─ Add all required stages
   ├─ Configure security scanning
   ├─ Setup monitoring
   └─ Make policies configurable

3. VALIDATE (up to 3 attempts)
   ├─ Lint pipeline syntax
   ├─ Test pipeline structure
   ├─ Verify all required stages
   └─ Check fail-fast criteria

4. DEPLOY
   ├─ Commit to new branch
   ├─ Open PR with description
   └─ Never merge (human review required)
```

---

## Key Principles

✅ **No Overwrite** - Check existing pipelines, repair instead of regenerate  
✅ **Configurable** - All fail-fast criteria and required steps configurable  
✅ **Validation Loop** - Up to 3 attempts before escalation  
✅ **Human Review** - Always require human approval before merge  
✅ **Security** - Mandatory SAST, SCA, DAST, image scanning  
✅ **Monitoring** - Integration with Dynatrace and Splunk  

---

**See also**:
- [Main README](../README.md)
- [QUICK_START.md](../QUICK_START.md)
