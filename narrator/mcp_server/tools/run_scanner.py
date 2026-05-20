"""MCP tool: run_scanner

Triggers the modeling-readiness-scanner notebook in Fabric via the
Fabric REST API (Run On Demand Notebook) and polls until completion.

Fabric API ref:
  POST /v1/workspaces/{workspaceId}/items/{itemId}/jobs/instances?jobType=RunNotebook
  GET  /v1/workspaces/{workspaceId}/items/{itemId}/jobs/instances/{jobInstanceId}

The caller must supply a Fabric API bearer token (scope:
  https://api.fabric.microsoft.com/user_impersonation)
— different from the OneLake token used by the other tools.
"""
from __future__ import annotations

import time
from typing import Any

import requests

FABRIC_API = "https://api.fabric.microsoft.com/v1"
POLL_INTERVAL_SEC = 10
MAX_WAIT_SEC = 30 * 60  # 30-minute ceiling; scanner typically completes in < 5 min


def run_scanner(
    workspace_id: str,
    notebook_id: str,
    fabric_token: str,
    workspace_id_param: str = "",
    workspace_url_param: str = "",
    poll: bool = True,
) -> dict:
    """Trigger the scanner notebook and optionally wait for completion.

    Args:
        workspace_id: Fabric workspace GUID that owns the notebook.
        notebook_id: Fabric item ID (GUID) of the scanner notebook.
        fabric_token: Bearer token with Fabric API scope.
        workspace_id_param: Value to inject into WORKSPACE_ID notebook parameter.
            If empty, the notebook's own pre-filled value is used.
        workspace_url_param: Value to inject into WORKSPACE_URL notebook parameter.
            If empty, the notebook's own pre-filled value is used.
        poll: If True, block until the job finishes and return the final status.
            If False, return immediately after submitting (returns job instance ID).

    Returns:
        {
            "status": "Succeeded" | "Failed" | "Cancelled" | "Submitted",
            "job_instance_id": "<guid>",
            "message": "<human-readable summary>",
        }
    """
    headers = {
        "Authorization": f"Bearer {fabric_token}",
        "Content-Type": "application/json",
    }

    body: dict[str, Any] = {"jobType": "RunNotebook"}

    # Inject notebook parameters when provided so the customer doesn't need
    # to open the notebook and edit Cell 1 manually.
    params: dict[str, dict] = {}
    if workspace_id_param:
        params["WORKSPACE_ID"] = {"value": workspace_id_param}
    if workspace_url_param:
        params["WORKSPACE_URL"] = {"value": workspace_url_param}
    if params:
        body["executionData"] = {"parameters": params}

    trigger_url = (
        f"{FABRIC_API}/workspaces/{workspace_id}/items/{notebook_id}"
        f"/jobs/instances?jobType=RunNotebook"
    )
    resp = requests.post(trigger_url, json=body, headers=headers, timeout=30)

    if resp.status_code not in (200, 202):
        return {
            "status": "Failed",
            "job_instance_id": "",
            "message": (
                f"Failed to trigger notebook: HTTP {resp.status_code} — {resp.text[:400]}"
            ),
        }

    # Fabric returns 202 Accepted with a Location header pointing to the job instance.
    location = resp.headers.get("Location", "")
    job_instance_id = location.rstrip("/").split("/")[-1] if location else ""

    if not poll:
        return {
            "status": "Submitted",
            "job_instance_id": job_instance_id,
            "message": (
                f"Notebook job submitted (id: {job_instance_id}). "
                "Poll the job status separately or re-run with poll=True."
            ),
        }

    # Poll until terminal state or timeout
    status_url = (
        f"{FABRIC_API}/workspaces/{workspace_id}/items/{notebook_id}"
        f"/jobs/instances/{job_instance_id}"
    )
    elapsed = 0
    while elapsed < MAX_WAIT_SEC:
        time.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC

        poll_resp = requests.get(status_url, headers=headers, timeout=30)
        if poll_resp.status_code != 200:
            continue

        data = poll_resp.json()
        job_status = data.get("status", "")

        if job_status in ("Succeeded", "Failed", "Cancelled", "Deduped"):
            failure_reason = ""
            if job_status != "Succeeded":
                failure_reason = data.get("failureReason", {}).get("message", "")
            return {
                "status": job_status,
                "job_instance_id": job_instance_id,
                "message": (
                    f"Scanner notebook {job_status.lower()} after {elapsed}s."
                    + (f" Reason: {failure_reason}" if failure_reason else "")
                ),
            }

    return {
        "status": "Timeout",
        "job_instance_id": job_instance_id,
        "message": (
            f"Scanner notebook did not complete within {MAX_WAIT_SEC}s. "
            f"Job instance: {job_instance_id}. Check Fabric for status."
        ),
    }
