"""Disables billing on this project once the budget's spend exceeds its amount.

Triggered by the Cloud Billing budget's Pub/Sub notifications. With DRY_RUN=true
it only checks that it is allowed to unlink billing and logs what it would do.
"""

import base64
import json
import os

import functions_framework
import google.auth
from google.auth.transport.requests import AuthorizedSession

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
DRY_RUN = os.environ.get("DRY_RUN", "").lower() == "true"

credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
session = AuthorizedSession(credentials)


@functions_framework.cloud_event
def stop_billing(cloud_event):
    notification = json.loads(base64.b64decode(cloud_event.data["message"]["data"]))
    cost = notification["costAmount"]
    budget = notification["budgetAmount"]
    print(f"cost={cost} budget={budget} dry_run={DRY_RUN}")

    if cost <= budget:
        return

    if DRY_RUN:
        check = session.post(
            f"https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT_ID}:testIamPermissions",
            json={"permissions": ["resourcemanager.projects.deleteBillingAssignment"]},
        )
        check.raise_for_status()
        print(f"DRY_RUN: would disable billing; held permissions: {check.json().get('permissions', [])}")
        return

    # An empty billing account name unlinks billing from the project.
    session.put(
        f"https://cloudbilling.googleapis.com/v1/projects/{PROJECT_ID}/billingInfo",
        json={"billingAccountName": ""},
    ).raise_for_status()
    print(f"Disabled billing for {PROJECT_ID}")
