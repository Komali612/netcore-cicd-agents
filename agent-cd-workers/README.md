# Agent CD Workers

CD pipeline generation agents for different technology stacks and deployment platforms.

## Agents in This Folder

### netcore-cd-agent
**Purpose**: Generate Harness deployment pipelines for .NET Core on AKS

**What it does**:
1. **Prepare** - Receives CI build output and extracts deployment config
2. **Design** - Creates Harness pipeline with shared template + per-app config
3. **Validate** - Validates pipeline with sandboxed dry-run (up to 3 attempts)
4. **Deploy** - Opens PR for human review

**Deployment Strategy**: Blue/Green on Kubernetes

**Pipeline Gates**:
1. Deploy - Pull image from Nexus, deploy to AKS using blue/green
2. Health Check - Verify health before traffic cutover
3. DAST - Run Fortify WebInspect security scan
4. Playwright - Run automated regression tests in ephemeral container
5. Finalize - Complete blue/green cutover

**Rollback Triggers**:
- Health check failure → Rollback to green
- DAST CVE above severity threshold → Rollback to green
- Critical test failure → Rollback to green

**How to run**:
```bash
cd netcore-cd-agent
uv sync
cp .env.example .env
# Edit .env with AGENT_MODEL and ANTHROPIC_API_KEY
uv run agent
```

**System Prompt**: `src/agent/prompts/system.md` (72 lines)
- Defines complete CD workflow
- Explains prepare, design, validate, deploy phases
- Pipeline gates and rollback logic
- Constraints: shared templates, ephemeral cleanup, human review

**Skills**: `src/agent/skills/` (4 files)
- Receive Handoff (CI output + config extraction)
- Design (Harness pipeline + config generation)
- Validate (schema check, sandboxed dry-run)
- Deploy (PR creation)

**Tools**: `src/agent/tools/tools.py` (4 implementations)
- `ReceiveCIHandoff()` - Receive CI output and deployment config
- `GenerateHarnessPipeline()` - Create pipeline template + config
- `ValidateDeploymentPipeline()` - Validate with sandboxed dry-run
- `CreateDeploymentPR()` - Open PR for review

---

## Adding New CD Workers

To add a CD worker for different platform (e.g., AWS, GCP, on-premise):

```bash
cp -r /Users/komalipyla/Desktop/agent/agent-starter aws-cd-agent
```

Then customize:
1. `pyproject.toml` - Update agent name, add platform-specific deps
2. `src/agent/prompts/system.md` - Define AWS deployment workflow
3. `src/agent/skills/*.md` - Define AWS-specific capabilities
4. `src/agent/tools/tools.py` - Implement AWS deployment logic

Example for AWS:
```
aws-cd-agent/
├── src/agent/prompts/system.md          (EC2/ECS/EKS deployment)
├── src/agent/skills/
│   ├── receive-handoff.md               (CI output handling)
│   ├── design-pipeline.md               (CloudFormation/Terraform)
│   ├── validate-deployment.md
│   └── deploy-pipeline.md
└── src/agent/tools/tools.py             (AWS CLI tools)
```

---

## CD Worker Pattern

All CD workers follow this pattern:

```
1. PREPARE
   ├─ Receive CI build output (image, SBOM, version)
   ├─ Clone repository
   ├─ Extract deployment configuration
   │  ├─ Cluster/infrastructure details
   │  ├─ App name, namespace, container specs
   │  ├─ Environment configuration
   │  ├─ Change management details
   │  ├─ Approvers and notification teams
   │  └─ Rollback reference image
   └─ Prepare for pipeline design

2. DESIGN
   ├─ Check for existing pipeline template
   ├─ Create/reuse shared pipeline template
   ├─ Generate per-app/environment configuration
   ├─ Define deployment gates
   ├─ Configure rollback logic
   ├─ Setup health checks
   └─ Add monitoring integration

3. VALIDATE (up to 3 attempts)
   ├─ Schema validation on template & config
   ├─ Lint configuration files
   ├─ Sandboxed dry-run:
   │  ├─ No real cluster connection
   │  ├─ No real image pull
   │  ├─ No real deployment
   │  ├─ No real security scans
   │  └─ No ephemeral containers created
   ├─ Verify all gate wiring
   └─ Ensure ephemeral cleanup logic

4. DEPLOY
   ├─ Commit pipeline template to new branch
   ├─ Commit per-app configuration to same branch
   ├─ Open PR with clear description
   ├─ Document shared template pattern
   └─ Never merge (human review required)
```

---

## Key Principles

✅ **No Template Forking** - Shared templates apply to all apps, no per-app forks  
✅ **Per-App Config** - Configuration files customize shared template (like Helm)  
✅ **Sandboxed Validation** - No real deployments during validation  
✅ **Automatic Rollback** - All gates wired to rollback on failure  
✅ **Ephemeral Cleanup** - Guaranteed cleanup of test containers  
✅ **Rollback Logging** - Every rollback logged with gate and reason  
✅ **Human Review** - Always require human approval before merge  
✅ **Monitoring** - Integration with Dynatrace and Splunk  

---

## Template Reusability

The shared template pattern enables:

**One shared template** for all apps of same type:
```yaml
# harness/pipelines/netcore-deployment-pipeline.yaml
# Single template used by multiple applications
```

**Multiple configuration files** for different apps/environments:
```yaml
# harness/config/app1-production.yaml
# harness/config/app1-staging.yaml
# harness/config/app2-production.yaml
# harness/config/app2-staging.yaml
# Each app/env reuses same template
```

This mirrors Helm chart + values file pattern for pipeline reusability.

---

**See also**:
- [Main README](../README.md)
- [QUICK_START.md](../QUICK_START.md)
