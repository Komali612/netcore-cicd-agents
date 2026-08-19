# Validate Deployment Pipeline Configuration

After generating the Harness pipeline and configuration, call the `validate_deployment_pipeline` tool to:
- Perform **schema validation** on both the Harness pipeline template and the per-app configuration file
- Lint the configuration files for correctness
- Run a **sandboxed dry-run** that:
  - Verifies the deployment pipeline structure is correct
  - Confirms stage ordering (Deploy → HealthCheck → DAST → Playwright → Finalize)
  - Tests the rollback wiring (health check, DAST, and Playwright paths)
  - **Does NOT** pull any real container image
  - **Does NOT** deploy to a real Kubernetes cluster
  - **Does NOT** run any real DAST scans against production
  - **Does NOT** execute Playwright tests against live infrastructure
- Verify that all three rollback paths are wired correctly
- Ensure ephemeral container cleanup logic is present

If validation fails, you will iterate:
1. Analyze the validation error
2. Call `generate_harness_pipeline` to fix the issue
3. Call `validate_deployment_pipeline` again

This cycle can repeat up to **3 total attempts**. If validation fails after 3 attempts, escalate to human review by creating an exception entry.

If validation succeeds, proceed to Deploy step.
