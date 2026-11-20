"""Synthetic-only policy identifiers — never present as production authorization."""

POLICY_ADAPTER = "synthetic_guest_v1"
POLICY_REVISION = "synthetic-policy-v1"
PERMISSION_REVISION = "permissions-v1"
PRODUCTION_AUTHORIZATION = False

# AuthZEN-style actions Alfred / workers must use.
ACTIONS = {
    "note.retrieve",
    "model.dispatch",
    "context.retrieve",
    "proposal.disclose",
    "excerpt.display",
    "excerpt.export",
    "review.apply",
    "evaluation.run",
    "audit.write",
    "audit.read",
    "case.read",
    "case.act",
    "analytics.read",
    "document.list",
    "outbox.read",
    "outbox.retry",
    "principal.revoke",
}

PATIENT_SCOPED_ACTIONS = {
    "note.retrieve",
    "model.dispatch",
    "context.retrieve",
    "proposal.disclose",
    "excerpt.display",
    "excerpt.export",
    "review.apply",
    "evaluation.run",
}

ROLE_ACTIONS: dict[str, frozenset[str]] = {
    "coordinator": frozenset(
        {
            "note.retrieve",
            "context.retrieve",
            "proposal.disclose",
            "excerpt.display",
            "evaluation.run",
            "audit.write",
            "audit.read",
            "case.read",
            "case.act",
            "analytics.read",
            "document.list",
            "outbox.read",
            "outbox.retry",
            "principal.revoke",
        }
    ),
    "clinical_reviewer": frozenset(
        {
            "note.retrieve",
            "context.retrieve",
            "proposal.disclose",
            "excerpt.display",
            "excerpt.export",
            "review.apply",
            "evaluation.run",
            "audit.write",
            "audit.read",
            "case.read",
            "case.act",
            "analytics.read",
            "document.list",
            "principal.revoke",
        }
    ),
    "population_analyst": frozenset({"analytics.read", "audit.write", "audit.read"}),
    "service": frozenset(
        {
            "note.retrieve",
            "model.dispatch",
            "proposal.disclose",
            "excerpt.display",
            "review.apply",
            "audit.write",
        }
    ),
}

# review.apply requires clinical_reviewer (enforced in PDP + review service)

PURPOSE_OF_USE = {
    "demo_care_coordination",
    "demo_clinical_review",
    "demo_population_analytics",
    "demo_model_extraction",
}

# Approved model destinations for this deployment (gated).
APPROVED_MODEL_DESTINATIONS = {
    "offline_fixture",
    "medgemma_hf_endpoint",  # only when live config is present
}

SERVICE_NAME = "namaa-api"
SERVICE_TOKEN_ENV = "NAMAA_SERVICE_TOKEN"
DEFAULT_SERVICE_TOKEN = "dev-synthetic-service-token-not-for-production"