# 12. Hybrid Execution Contract

## Purpose

Solunex uses a hybrid execution architecture.

Temporal owns durable workflow execution.

LangGraph owns agent reasoning.

The boundary between them is an explicit request/result contract.

Temporal invokes an agentic task by providing an `AgentTask`.

LangGraph processes the task and returns an `AgentResult`.

Temporal then uses the result to determine the next durable workflow step.

---

# Canonical Flow

    Temporal Workflow
           │
           │ AgentTask
           ▼
      LangGraph Agent
           │
           │ AgentResult
           ▼
    Temporal Workflow
           │
           ▼
      Next Activity


The boundary is therefore:

    Temporal
       ↓
    AgentTask
       ↓
    LangGraph
       ↓
    AgentResult
       ↓
    Temporal
       ↓
    Next Activity

---

# AgentTask

`AgentTask` represents a request from the durable workflow layer to
the agentic reasoning layer.

Conceptually:

    AgentTask
    ├── task_id
    ├── task_type
    ├── context
    └── metadata


The exact fields are implementation details and must be finalized before
the contract is shared across services.

The task must contain sufficient context for the LangGraph agent to make
the requested decision.

---

# AgentResult

`AgentResult` represents the structured result returned by LangGraph.

Conceptually:

    AgentResult
    ├── task_id
    ├── action
    ├── reason
    └── data


The result must be structured and machine-readable.

Temporal must not need to interpret free-form LLM text to determine the
next workflow operation.

---

# Example

A video workflow may execute:

    Temporal
       │
       ├── Research Activity
       │
       ▼
    Research Result
       │
       ▼
    Director Agent Activity
       │
       │ AgentTask
       ▼
    ┌───────────────────────┐
    │      LangGraph        │
    │                       │
    │ Analyze Intent        │
    │       ↓               │
    │ Determine Next Stage  │
    └───────────┬───────────┘
                │
                │ AgentResult
                ▼
    Temporal Workflow
                │
                ▼
          Next Activity


---

# Responsibility Boundary

## Temporal

Temporal is responsible for:

- invoking the agent activity
- durable workflow state
- activity execution
- retries
- timeouts
- workflow lifecycle
- human waits
- recovery
- deciding how the workflow continues after `AgentResult`

Temporal does not perform the agent's reasoning itself.

---

## LangGraph

LangGraph is responsible for:

- agent state
- reasoning flow
- planning
- tool selection
- conditional reasoning branches
- bounded agent loops
- evaluation
- multi-agent coordination
- producing `AgentResult`

LangGraph does not own durable workflow execution.

---

# Agent Activity Boundary

The Temporal workflow should invoke the agent through an activity boundary.

Conceptually:

    Temporal Workflow
          │
          ▼
    Director Agent Activity
          │
          ▼
    AgentTask
          │
          ▼
    LangGraph
          │
          ▼
    AgentResult
          │
          ▼
    Director Agent Activity
          │
          ▼
    Temporal Workflow


The activity is the integration boundary.

The LangGraph process must not directly manipulate Temporal workflow state.

---

# Structured Result Rule

The LangGraph agent must return a structured result.

Preferred:

    {
        "action": "START_RESEARCH",
        "reason": "Project requires research before creative planning."
    }


Not:

    "I think we should probably start with some research..."


Temporal should receive a deterministic, machine-readable representation
of the agent's decision.

---

# Execution Rule

An `AgentResult` describes what should happen next.

It does not directly execute the requested operation.

For example:

    AgentResult
        ↓
    action = GENERATE_SHOT
        ↓
    Temporal Workflow
        ↓
    Generate Shot Activity
        ↓
    Worker


The agent therefore decides.

Temporal executes.

Workers perform the actual operation.

---

# Error Handling

If LangGraph fails while producing an `AgentResult`:

    Temporal
       ↓
    Director Agent Activity
       ↓
    LangGraph
       ↓
    failure
       ↓
    Temporal retry / failure policy


The agent process does not own infrastructure recovery.

If a downstream activity fails:

    Worker
       ↓
    Activity failure
       ↓
    Temporal
       ↓
    Retry / timeout / escalation


LangGraph may later receive the resulting state and reason about the
next action.

---

# Idempotency Boundary

Agent activities must participate in the system's idempotency model.

A Temporal retry must not accidentally create a duplicate paid operation.

Conceptually:

    Temporal Retry
         ↓
    Agent Activity
         ↓
    Idempotency Check
         ↓
    Existing Result?
       ├── yes → reuse
       └── no  → execute


The idempotency implementation is defined separately from this contract.

---

# Human Decision Boundary

If LangGraph determines that human input is required:

    LangGraph
       ↓
    AgentResult
       ↓
    Temporal
       ↓
    Human Wait
       ↓
    Human Decision
       ↓
    Temporal resumes
       ↓
    LangGraph when reasoning is required again


The LangGraph process does not remain alive while waiting for the human.

---

# Canonical Hybrid Model

    ┌───────────────────────────────┐
    │          Temporal             │
    │                               │
    │  Durable execution            │
    │  Workflow state               │
    │  Retry / timeout              │
    │  Human wait                   │
    │  Activity execution           │
    └───────────────┬───────────────┘
                    │
                 AgentTask
                    │
                    ▼
    ┌───────────────────────────────┐
    │          LangGraph            │
    │                               │
    │  Agent state                  │
    │  Reasoning                    │
    │  Planning                     │
    │  Tool selection               │
    │  Evaluation                   │
    │  Agent coordination           │
    └───────────────┬───────────────┘
                    │
                 AgentResult
                    │
                    ▼
    ┌───────────────────────────────┐
    │          Temporal             │
    │                               │
    │  Interpret structured result  │
    │  Select next workflow step    │
    │  Execute next activity        │
    └───────────────────────────────┘


# Critical Invariant

The boundary is always:

    AgentTask → LangGraph → AgentResult

LangGraph decides what should happen.

Temporal decides how that decision is executed durably.

Workers perform the actual infrastructure operation.

This contract prevents LangGraph from becoming the workflow engine and
prevents Temporal from becoming the agent reasoning engine.
