import pytest
from pydantic import ValidationError

from packages.contracts.policy import PolicyStatus, PolicyVersion


def valid_policy() -> PolicyVersion:
    return PolicyVersion(
        version=14,
        rule="Mystery hooks outperform fact hooks for ocean videos.",
        evidence="17 videos",
        confidence=0.87,
        status=PolicyStatus.ACTIVE,
    )


def test_valid_policy_is_accepted():
    policy = valid_policy()

    assert policy.version == 14
    assert policy.status == PolicyStatus.ACTIVE


def test_invalid_confidence_is_rejected():
    with pytest.raises(ValidationError):
        PolicyVersion(
            version=14,
            rule="Mystery hooks outperform fact hooks.",
            evidence="17 videos",
            confidence=1.5,
            status=PolicyStatus.ACTIVE,
        )


def test_missing_rule_is_rejected():
    with pytest.raises(ValidationError):
        PolicyVersion(
            version=14,
            evidence="17 videos",
            confidence=0.87,
            status=PolicyStatus.ACTIVE,
        )
