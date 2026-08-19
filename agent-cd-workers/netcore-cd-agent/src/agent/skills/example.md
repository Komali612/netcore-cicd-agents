# Receive CI Handoff and Extract Deployment Configuration

When triggered by the orchestrator agent with a Git repository URL, call the `receive_ci_handoff` tool to:
- Read the CI agent's output (image location, tag pattern, SBOM reference)
- Clone and analyze the repository for deployment configuration
- Extract from config files:
  - Kubernetes cluster details (cluster name, namespace, pod/app/container names)
  - CI image location and version
  - Artifact storage repository details
  - Environment configuration
  - Change management request details for PROD
  - Deployment approver contact details
  - Notification team details
  - Current production build image for rollback reference

This information will guide the pipeline design and configuration generation.
