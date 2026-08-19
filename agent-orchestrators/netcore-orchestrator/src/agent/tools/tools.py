"""Tools for NetCore Orchestrator — the code the LLM can call.

This orchestrator provides a unified UI for users to select and run
either the CI agent or CD agent based on their needs.
"""
from agent_core import Tool
import json
from typing import Optional


class RunCIAgent(Tool):
    """Trigger the NetcoreCIAgent to generate CI pipeline."""

    name = "run_ci_agent"
    description = """Trigger the NetcoreCIAgent to generate a GitHub Actions CI pipeline
    for the provided .NET Core repository. The agent will discover the project structure,
    generate a pipeline with build, test, security scanning, and container image steps."""
    parameters = {
        "type": "object",
        "properties": {
            "repo_url": {
                "type": "string",
                "description": "Git repository URL (e.g., https://github.com/user/repo.git)"
            },
            "branch": {
                "type": "string",
                "description": "Branch to analyze (default: main)",
                "default": "main"
            },
            "include_dast": {
                "type": "boolean",
                "description": "Include DAST scanning in CI pipeline (default: true)",
                "default": True
            },
            "open_pr": {
                "type": "boolean",
                "description": "Open a pull request with the generated workflow (default: true). "
                               "When false, the workflow is generated but no PR is opened.",
                "default": True
            },
            "allow_llm_fallback": {
                "type": "boolean",
                "description": "If Discover cannot match the repository to a built-in .NET "
                               "template, let the LLM author the workflow instead of writing "
                               "the repo to the exception list (default: false).",
                "default": False
            }
        },
        "required": ["repo_url"],
    }

    def run(self, repo_url: str, branch: str = "main", include_dast: bool = True,
            open_pr: bool = True, allow_llm_fallback: bool = False) -> dict:
        """Run the CI agent."""
        return {
            "status": "ci_agent_initiated",
            "repo_url": repo_url,
            "branch": branch,
            "agent": "NetcoreCIAgent",
            "action": "Generate GitHub Actions CI Pipeline",
            "workflow": {
                "step_1": "Discover project structure and framework",
                "step_2": "Generate GitHub Actions workflow",
                "step_3": "Validate workflow syntax and structure",
                "step_4": "Open pull request for human review"
            },
            "pipeline_stages": [
                "Build (.NET CLI/MSBuild/NuGet)",
                "Unit Tests",
                "SonarQube Code Coverage",
                "SAST (Fortify)",
                "SCA (Sonatype)",
                "DAST (Fortify WebInspect)" if include_dast else "DAST (disabled)",
                "Docker Image Build & Scan (Wiz)",
                "SBOM Generation",
                "Nexus Artifact Storage",
                "Helm Chart Update",
                "Dynatrace & Splunk Monitoring"
            ],
            "options": {
                "dast_enabled": include_dast,
                "docker_enabled": True,
                "helm_enabled": True,
                "open_pr": open_pr,
                "allow_llm_fallback": allow_llm_fallback,
                "monitoring": ["dynatrace", "splunk"]
            },
            "next_steps": [
                "Agent will analyze the repository",
                "GitHub Actions workflow will be generated",
                ("PR will be opened for your review" if open_pr
                 else "Workflow generated only — no PR opened (open_pr=false)"),
                "Merge the PR when ready to activate the pipeline"
            ],
            "placeholder_notice": "This is a placeholder response. In production, this would invoke the actual NetcoreCIAgent service with the provided repository URL."
        }


class RunCDAgent(Tool):
    """Trigger the NetcoreCDAgent to generate CD pipeline."""

    name = "run_cd_agent"
    description = """Trigger the NetcoreCDAgent to generate a Harness CD pipeline
    for the provided .NET Core repository. The agent will create a blue/green deployment
    pipeline with health checks, DAST gate, Playwright test gate, and automatic rollback."""
    parameters = {
        "type": "object",
        "properties": {
            "repo_url": {
                "type": "string",
                "description": "Git repository URL (e.g., https://github.com/user/repo.git)"
            },
            "kubernetes_cluster": {
                "type": "string",
                "description": "Target Kubernetes cluster name",
                "default": "aks-prod-cluster"
            },
            "namespace": {
                "type": "string",
                "description": "Target Kubernetes namespace",
                "default": "default"
            },
            "include_dast": {
                "type": "boolean",
                "description": "Include DAST security gate (default: true)",
                "default": True
            },
            "include_playwright": {
                "type": "boolean",
                "description": "Include Playwright test gate (default: true)",
                "default": True
            },
            "open_pr": {
                "type": "boolean",
                "description": "Open a pull request with the generated pipeline (default: true).",
                "default": True
            },
            "auto_deploy": {
                "type": "boolean",
                "description": "Deploy straight to production when true; when false, insert a "
                               "click-to-approve gate before the production cutover (default: false).",
                "default": False
            },
            "auto_handoff": {
                "type": "boolean",
                "description": "Run CD automatically right after CI completes (true), or only when "
                               "triggered manually from GitHub Actions (false) (default: true).",
                "default": True
            },
            "allow_llm_fallback": {
                "type": "boolean",
                "description": "If no built-in deploy recipe matches the application shape, let the "
                               "LLM author one instead of escalating (default: false).",
                "default": False
            }
        },
        "required": ["repo_url"],
    }

    def run(self, repo_url: str, kubernetes_cluster: str = "aks-prod-cluster",
            namespace: str = "default", include_dast: bool = True,
            include_playwright: bool = True, open_pr: bool = True,
            auto_deploy: bool = False, auto_handoff: bool = True,
            allow_llm_fallback: bool = False) -> dict:
        """Run the CD agent."""
        return {
            "status": "cd_agent_initiated",
            "repo_url": repo_url,
            "kubernetes_cluster": kubernetes_cluster,
            "namespace": namespace,
            "agent": "NetcoreCDAgent",
            "action": "Generate Harness CD Pipeline",
            "approval_to_production": "automatic" if auto_deploy else "click-to-approve gate",
            "cd_handoff": "auto — right after CI" if auto_handoff else "manual — in GitHub Actions",
            "workflow": {
                "step_1": "Receive CI handoff and extract deployment config",
                "step_2": "Generate Harness pipeline template and configuration",
                "step_3": "Validate pipeline structure and gates",
                "step_4": "Open pull request for human review"
            },
            "deployment_strategy": "blue-green",
            "pipeline_gates": [
                "Deploy - Pull image and deploy to AKS",
                "Health Check - Verify health before traffic cutover",
                "DAST - Run Fortify WebInspect scan" if include_dast else "DAST (disabled)",
                "Playwright - Run automated regression tests" if include_playwright else "Playwright (disabled)",
                "Finalize - Complete blue/green cutover"
            ],
            "rollback_paths": [
                "Health check failure → Rollback to green",
                "DAST CVE threshold exceeded → Rollback to green" if include_dast else None,
                "Critical Playwright test failure → Rollback to green" if include_playwright else None
            ],
            "monitoring": {
                "dynatrace": "Pod status, memory, CPU utilization alerts",
                "splunk": "API routing, security logs, threat detection, application failures"
            },
            "options": {
                "dast_enabled": include_dast,
                "playwright_enabled": include_playwright,
                "open_pr": open_pr,
                "auto_deploy": auto_deploy,
                "auto_handoff": auto_handoff,
                "allow_llm_fallback": allow_llm_fallback,
                "ephemeral_container_cleanup": "guaranteed"
            },
            "next_steps": [
                "Agent will extract deployment configuration from your repository",
                "Harness pipeline template and config will be generated",
                "PR will be opened for your review",
                "Merge the PR to activate the deployment pipeline"
            ],
            "requirements": [
                "CI pipeline must be successfully run first",
                "Kubernetes cluster must be accessible",
                "Deployment config files must be present in repository",
                "Required secrets must be configured in Harness"
            ],
            "placeholder_notice": "This is a placeholder response. In production, this would invoke the actual NetcoreCDAgent service with the provided repository and deployment details."
        }


class DisplayOrchestratorUI(Tool):
    """Display the orchestrator UI to the user."""

    name = "display_orchestrator_ui"
    description = "Display the unified CI/CD orchestrator interface with input fields and action buttons."
    parameters = {
        "type": "object",
        "properties": {
            "show_ui": {
                "type": "boolean",
                "description": "Display the orchestrator UI",
                "default": True
            }
        }
    }

    def run(self, show_ui: bool = True) -> dict:
        """Display the orchestrator UI."""
        if not show_ui:
            return {"status": "ui_hidden"}

        return {
            "status": "orchestrator_ui_displayed",
            "interface": {
                "title": ".NET Core CI/CD Pipeline Automation",
                "description": "Generate GitHub Actions CI pipelines or Harness CD pipelines for your .NET Core applications",
                "sections": [
                    {
                        "name": "Repository Input",
                        "type": "input",
                        "label": "Git Repository URL",
                        "placeholder": "https://github.com/your-org/your-repo.git",
                        "required": True,
                        "help": "Enter the HTTPS URL of your Git repository"
                    },
                    {
                        "name": "CI Pipeline Section",
                        "type": "card",
                        "title": "CI Pipeline Generation",
                        "description": "Generate a GitHub Actions CI pipeline that builds, tests, scans, and produces container images",
                        "features": [
                            "✓ Discover .NET Core project structure",
                            "✓ Build with .NET CLI, MSBuild, or NuGet",
                            "✓ Run unit tests with SonarQube coverage",
                            "✓ SAST, SCA, DAST security scanning",
                            "✓ Docker image build and scanning (Wiz)",
                            "✓ SBOM generation",
                            "✓ Artifact storage in Nexus",
                            "✓ Helm chart updates for AKS",
                            "✓ Dynatrace & Splunk monitoring"
                        ],
                        "button": {
                            "label": "Run CI Agent",
                            "action": "run_ci_agent",
                            "style": "primary"
                        }
                    },
                    {
                        "name": "CD Pipeline Section",
                        "type": "card",
                        "title": "CD Pipeline Generation",
                        "description": "Generate a Harness deployment pipeline with blue/green strategy and automatic gates",
                        "features": [
                            "✓ Blue/green deployment strategy",
                            "✓ Health check gate before traffic cutover",
                            "✓ DAST security scanning gate",
                            "✓ Playwright automated test gate",
                            "✓ Automatic rollback on gate failure",
                            "✓ Ephemeral container cleanup guaranteed",
                            "✓ Dynatrace & Splunk monitoring",
                            "✓ Shared template per application pattern",
                            "✓ Per-app/environment configuration"
                        ],
                        "button": {
                            "label": "Run CD Agent",
                            "action": "run_cd_agent",
                            "style": "primary"
                        }
                    }
                ]
            },
            "user_instructions": [
                "1. Enter your Git repository URL in the input field",
                "2. Choose your action: Run CI Agent or Run CD Agent",
                "3. The agent will process your repository",
                "4. A pull request will be opened for your review",
                "5. Merge the PR when satisfied with the generated pipeline"
            ],
            "notes": {
                "ci_agent": "Recommended for first-time setup of .NET Core repositories",
                "cd_agent": "Requires prior CI pipeline generation and successful CI build",
                "user_choice": "You decide which agent to run - no automatic routing"
            }
        }


class GetAgentStatus(Tool):
    """Get the current status of a running agent."""

    name = "get_agent_status"
    description = "Get the current execution status and progress of a running CI or CD agent."
    parameters = {
        "type": "object",
        "properties": {
            "agent_name": {
                "type": "string",
                "description": "Name of the agent (netcore-ci-agent or netcore-cd-agent)",
                "enum": ["netcore-ci-agent", "netcore-cd-agent"]
            },
            "repo_url": {
                "type": "string",
                "description": "The repository URL being processed"
            }
        },
        "required": ["agent_name", "repo_url"],
    }

    def run(self, agent_name: str, repo_url: str) -> dict:
        """Get agent status."""
        return {
            "status": "agent_status_placeholder",
            "agent": agent_name,
            "repo_url": repo_url,
            "current_status": "in_progress",
            "progress": {
                "completed_steps": [],
                "current_step": "Analyzing repository structure",
                "remaining_steps": [],
                "completion_percentage": 35
            },
            "estimated_time_remaining": "2-3 minutes",
            "placeholder_notice": "This is a placeholder. In production, this would query the actual agent service for real status updates."
        }


# The framework loads this list. Add or remove tools here.
TOOLS = [
    DisplayOrchestratorUI(),
    RunCIAgent(),
    RunCDAgent(),
    GetAgentStatus(),
]
