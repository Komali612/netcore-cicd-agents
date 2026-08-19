# Design and Generate Harness Deployment Pipeline

When you have extracted the deployment configuration, call the `generate_harness_pipeline` tool to:
- Check if a Harness pipeline template already exists for this application pattern (reuse if found)
- Author a **shared pipeline template** (one template per application pattern, not per application)
- Generate **per-application/per-environment configuration files** (similar to Helm values files)
- Include all deployment gates:
  - **Deploy Gate**: Pull image from Nexus, deploy to AKS using blue/green strategy
  - **Health Check Gate**: Verify health before traffic cutover; rollback on failure
  - **DAST Gate**: Run Fortify WebInspect; rollback if CVE severity threshold exceeded
  - **Playwright Gate**: Run automated regression tests in ephemeral container; rollback on critical failure
  - **Finalization**: Complete blue/green cutover if no rollback triggered
- Configure Dynatrace and Splunk monitoring
- Generate pod health check logic
- Provision ephemeral test container with guaranteed cleanup

The configuration file should parameterize:
- Target Kubernetes namespace
- Image registry and tag reference
- DAST severity thresholds
- Test suite configuration
- Environment-specific variables
- Approver and notification contacts

This approach mirrors a Helm chart + values files pattern for pipeline reusability.
