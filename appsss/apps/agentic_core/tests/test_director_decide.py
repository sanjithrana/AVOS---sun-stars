from agentic_core.director.context_manager import build_project_summary
from agentic_core.director.director import DirectorAction, PipelineState, StudioDirector


def _summary(**overrides):
    base = dict(
        project_id="p1",
        topic="Flowers",
        duration_seconds=30,
        aspect_ratio="9:16",
        status="planning",
        budget_limit=None,
        budget_spent=0,
    )
    base.update(overrides)
    return build_project_summary(**base)


director = StudioDirector()


def test_fresh_project_researches_first():
    decision = director.decide(_summary(), PipelineState())
    assert decision.action == DirectorAction.RESEARCH
    assert "Flowers" in decision.reason


def test_mentions_prior_memory_when_present():
    decision = director.decide(_summary(prior_memory=["a", "b"]), PipelineState())
    assert "2 related memories" in decision.reason


def test_writes_script_after_research():
    decision = director.decide(_summary(), PipelineState(has_research=True))
    assert decision.action == DirectorAction.WRITE_SCRIPT
    assert "30s" in decision.reason


def test_waits_for_human_while_gate_pending():
    state = PipelineState(has_research=True, has_script=True, script_gate_status="pending")
    assert director.decide(_summary(), state).action == DirectorAction.AWAIT_HUMAN


def test_generates_audio_after_approval():
    state = PipelineState(has_research=True, has_script=True, script_gate_status="approved")
    assert director.decide(_summary(), state).action == DirectorAction.GENERATE_AUDIO


def test_stops_on_rejection():
    state = PipelineState(has_research=True, has_script=True, script_gate_status="rejected")
    assert director.decide(_summary(), state).action == DirectorAction.STOP


def test_stops_when_budget_exhausted():
    decision = director.decide(_summary(budget_limit=1.0, budget_spent=1.0), PipelineState())
    assert decision.action == DirectorAction.STOP
    assert "Budget" in decision.reason


def test_done_when_audio_exists():
    state = PipelineState(
        has_research=True, has_script=True, script_gate_status="approved", has_audio=True
    )
    assert director.decide(_summary(), state).action == DirectorAction.DONE
