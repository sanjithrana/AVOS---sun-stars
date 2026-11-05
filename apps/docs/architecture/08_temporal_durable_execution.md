# 8. Temporal Owns Durable Execution

## Purpose

Temporal is the durable execution layer of Solunex.

LangGraph is responsible for agentic reasoning, planning, stateful decision-making,
and selecting what should happen.

Temporal is responsible for making execution durable, recoverable, retryable,
and long-running.

The two responsibilities must remain separate.

---

## Temporal owns

Temporal is the system of record for durable workflow execution.

### 1. Workflow state

Temporal owns the state required to resume a workflow safely after interruption.

Examples:

- current workflow step
- workflow progress
- activity execution state
- retry state
- waiting state
- workflow completion state
- workflow failure state

Application-level business state may also be persisted in Solunex databases,
but workflow execution state belongs to Temporal.

---

### 2. Retries

Temporal owns retry behavior for activities and workflow execution.

Retries must be deterministic and bounded.

A retry must not create duplicate side effects.

For generation operations, idempotency must be enforced before execution so that:

    Temporal retry
        ↓
    idempotency check
        ↓
    existing result?
       ├── yes → reuse existing result
       └── no  → execute generation

A Temporal retry must never result in an unintended second paid generation.

---

### 3. Timeouts

Temporal owns execution timeouts.

This includes:

- activity timeouts
- workflow timeouts
- execution deadlines
- retry backoff
- failure handling associated with timeout conditions

Workers must not implement their own independent workflow lifecycle.

---

### 4. Human waits

Temporal owns durable waiting for human decisions.

Examples:

- approval
- rejection
- review
- escalation
- human override

The workflow must be able to pause and later resume without requiring
the agent process to remain alive.

The Director/agent must yield when waiting for a human decision.

Temporal resumes the workflow when the required signal or external event arrives.

---

### 5. Workflow lifecycle

Temporal owns the lifecycle of long-running workflows.

Conceptually:

    START
      ↓
    RUNNING
      ↓
    WAITING
      ↓
    RUNNING
      ↓
    COMPLETED

Failure paths may transition into retry, escalation, cancellation,
or terminal failure according to workflow policy.

The workflow lifecycle must not be managed by LangGraph.

---

### 6. Activity execution

Temporal owns dispatching activities to workers.

Activities represent deterministic execution boundaries around external work.

Examples:

    GenerateAudioActivity
    RenderBlenderActivity
    GenerateVideoActivity
    RunQAActivity
    AssembleVideoActivity

The exact activity names are defined by the corresponding workflow contracts.

Workers perform the actual infrastructure work.

---

### 7. Recovery

Temporal owns recovery from process, worker, and infrastructure interruptions
within the workflow's configured durability and retry model.

If a worker process disappears:

    Worker failure
        ↓
    Temporal detects activity failure/timeout
        ↓
    Retry policy
        ↓
    Activity executes again
        ↓
    Workflow continues

Recovery must not depend on keeping the LangGraph process alive.

---

# Responsibility Boundary

The Solunex hybrid architecture follows:

    ┌─────────────────────────────┐
    │          Director           │
    │       Agent / LLM           │
    │                             │
    │  Reasoning                  │
    │  Planning                   │
    │  Decision making             │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │         LangGraph            │
    │                             │
    │  Agent state                │
    │  Reasoning graph            │
    │  Conditional decisions      │
    │  Tool selection             │
    │  Execution intent           │
    └──────────────┬──────────────┘
                   │
                   │ typed execution intent
                   ▼
    ┌─────────────────────────────┐
    │          Temporal            │
    │                             │
    │  Workflow state             │
    │  Retries                    │
    │  Timeouts                   │
    │  Human waits                │
    │  Workflow lifecycle         │
    │  Activity execution         │
    │  Recovery                   │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │           Workers            │
    │                             │
    │  Blender                    │
    │  ComfyUI                    │
    │  TTS                        │
    │  Whisper                    │
    │  QA                         │
    │  Rendering                  │
    └─────────────────────────────┘


# What LangGraph must NOT own

LangGraph must not become the durable workflow engine.

LangGraph must not own:

- infrastructure retry loops
- long-running workflow waiting
- human approval persistence
- worker recovery
- workflow lifecycle
- activity scheduling
- paid-generation retry semantics
- infrastructure subprocess execution

LangGraph may decide that an action is required.

Temporal is responsible for making that action execute durably.

---

# What Workers must NOT own

Workers must not become workflow orchestrators.

Workers perform bounded activities requested through the execution layer.

Workers must not independently decide:

- workflow ordering
- workflow retries
- human waiting
- workflow completion
- global workflow lifecycle

---

# Canonical Hybrid Rule

The architecture is:

    LangGraph
        =
    THINK / PLAN / DECIDE / ROUTE

    Temporal
        =
    EXECUTE / WAIT / RETRY / RECOVER / DURABILITY

    Workers
        =
    PERFORM THE ACTUAL WORK


# Critical Invariant

The agentic layer can request work.

The agentic layer cannot directly control durable infrastructure execution.

Temporal is the authoritative owner of durable execution.

Therefore:

    LLM
      ↓
    LangGraph
      ↓
    Execution Intent
      ↓
    Temporal Workflow
      ↓
    Temporal Activity
      ↓
    Worker
      ↓
    Result
      ↓
    Event / Workflow State
      ↓
    LangGraph when further reasoning is required


# Design Principle

Keep the boundary explicit.

LangGraph answers:

    "What should happen next?"

Temporal answers:

    "How do we execute that reliably over time?"

Workers answer:

    "How do we perform the requested operation?"

This separation prevents agent reasoning, workflow durability,
and infrastructure execution from becoming tightly coupled.
