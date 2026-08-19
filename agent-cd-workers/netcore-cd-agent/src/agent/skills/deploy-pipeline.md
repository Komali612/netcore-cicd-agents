# Commit Pipeline to Repository and Open Pull Request

After validation succeeds, call the `create_deployment_pr` tool to:
- Commit the Harness pipeline template to a new branch
- Commit the per-application/per-environment configuration file to the same branch
- Store the pipeline in a remote Git repository (via Harness Git Experience or equivalent)
  - Template stored as: `harness/pipelines/<pipeline-template-name>.yaml`
  - Config stored as: `harness/config/<app-name>-<environment>.yaml`
- Open a pull request against the main branch with a clear description including:
  - Overview of the shared pipeline template
  - Description of how to customize via configuration files
  - Deployment gates and rollback paths
  - Required environment variables and secrets
  - How to add new applications to this pipeline pattern
  - Next steps for the repository owner

**CRITICAL CONSTRAINT**: Never merge the PR yourself. The deployment pipeline is ready for human review only.

Report the PR URL and status back to the user for manual approval and merge.
