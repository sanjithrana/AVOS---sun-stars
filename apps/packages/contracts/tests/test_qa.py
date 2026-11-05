from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.contracts.qa import (
    QADimension,
    QADimensionResult,
    QAIssue,
    QARequest,
    QAResult,
    QAStatus,
)


def valid_qa_request() -> QARequest:
    return QARequest(
        shot_id=uuid4(),
        video_asset_id=uuid4(),
    )


def valid_qa_result() -> QAResult:
    return QAResult(
        shot_id=uuid4(),
        video_asset_id=uuid4(),
        status=QAStatus.PASS,
        score=0.95,
        confidence=0.90,
        evidence={},
        dimensions=[
            QADimensionResult(
                dimension=QADimension.VISUAL,
                score=0.95,
                confidence=0.90,
                diagnostics={},
                issues=[],
            )
        ],
    )


def test_valid_qa_is_accepted():
    result = valid_qa_result()

    assert result.status == QAStatus.PASS
    assert result.score == 0.95


def test_invalid_qa_dimension_is_rejected():
    with pytest.raises(ValidationError):
        QADimensionResult(
            dimension="not_a_dimension",
            score=0.5,
        )


def test_missing_video_asset_id_is_rejected():
    with pytest.raises(ValidationError):
        QARequest(
            shot_id=uuid4(),
        )
