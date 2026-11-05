from packages.contracts.script import Script, ScriptValidationIssue

MAX_DURATION_DRIFT_RATIO = 0.35  # scenes may total up to 35% off target


def validate_script(
    script: Script,
    *,
    target_duration_seconds: int | None = None,
) -> list[ScriptValidationIssue]:
    """
    Validate a generated Script.

    Returns a list of issues (possibly empty). Callers decide whether
    "error"-severity issues should block approval; "warning" issues are
    informational only.
    """
    issues: list[ScriptValidationIssue] = []

    if not script.scenes:
        issues.append(
            ScriptValidationIssue(severity="error", message="Script has no scenes.")
        )
        return issues

    for scene in script.scenes:
        if not scene.narration.strip():
            issues.append(
                ScriptValidationIssue(
                    severity="error",
                    message=f"Scene {scene.index} has empty narration.",
                )
            )
        if scene.estimated_seconds <= 0:
            issues.append(
                ScriptValidationIssue(
                    severity="error",
                    message=f"Scene {scene.index} has non-positive duration.",
                )
            )

    if target_duration_seconds:
        drift = abs(script.total_estimated_seconds - target_duration_seconds)
        ratio = drift / target_duration_seconds
        if ratio > MAX_DURATION_DRIFT_RATIO:
            issues.append(
                ScriptValidationIssue(
                    severity="warning",
                    message=(
                        f"Estimated duration ({script.total_estimated_seconds:.1f}s) "
                        f"drifts {ratio:.0%} from target ({target_duration_seconds}s)."
                    ),
                )
            )

    return issues


def has_blocking_errors(issues: list[ScriptValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)
