# 9. LangGraph Owns Agent Reasoning

## Purpose

LangGraph is the agentic reasoning layer of Solunex.

It is responsible for deciding what should happen next, maintaining agent
reasoning state, selecting tools, evaluating intermediate results, and
coordinating agentic decision flows.

LangGraph does not replace Temporal.

Temporal remains responsible for durable workflow execution, retries,
timeouts, human waits, workflow lifecycle, activity execution, and recovery.

The two responsibilities must remain explicitly separated.

---

# LangGraph owns

## 1. Agent state

LangGraph owns the state required for the agentic reasoning process.

This may include:

- current reasoning context
- planning state
- intermediate decisions
- observations
- tool results
- evaluation results
- agent coordination state
- decision history required by the graph

Agent state exists to support reasoning and decision-making.

Durable workflow execution state remains owned by Temporal.

---

## 2. Reasoning flow

LangGraph owns the reasoning graph.

A reasoning flow may conceptually look like:

    Input
      ↓
    Understand
      ↓
    Plan
      ↓
    Evaluate
      ↓
    Decide
      ↓
    Select Tool
      ↓
    Observe Result
      ↓
    Evaluate
      ↓
    Continue / Finish


The graph determines the logical reasoning path.

The graph does not directly execute infrastructure.

---

## 3. Tool selection

LangGraph decides which available tool or capability should be used.

Conceptually:

    Agent
      ↓
    Tool Selection
      ↓
    Typed Tool Request
      ↓
    Execution Boundary


The agent may select:

- audio generation
- shot planning
- Blender rendering
- video generation
- QA
- repair
- assembly

However, selecting a tool does not mean the agent directly executes the
underlying infrastructure.

Tool execution must cross the appropriate execution boundary.

---

## 4. Conditional branches

LangGraph owns agent-level conditional decisions.

Examples:

    QA result
       │
       ├── passed → continue
       │
       └── failed → reason about repair


Another example:

    Planning result
       │
       ├── sufficient → execute
       │
       └── insufficient → gather more information


These branches represent reasoning decisions.

They are different from Temporal workflow lifecycle transitions.

---

## 5. Agent loops

LangGraph owns bounded agentic reasoning loops.

Example:

    Observe
       ↓
    Reason
       ↓
    Act
       ↓
    Observe
       ↓
    Reason
       ↓
    Finish


Loops must remain bounded by explicit application policy.

LangGraph must not be used as an uncontrolled polling mechanism for
long-running infrastructure work.

When execution requires durable waiting, the agent yields to Temporal.

---

## 6. Evaluation

LangGraph owns agent-level evaluation and decision-making based on results.

Examples:

- evaluate a generated plan
- evaluate whether additional reasoning is required
- evaluate tool results
- determine whether a result satisfies the current objective
- determine whether another agent should be consulted
- determine whether execution should continue

Evaluation produces a decision or execution intent.

It does not directly control infrastructure.

---

## 7. Multi-agent coordination

LangGraph owns coordination between multiple agents when a workflow
requires multiple reasoning roles.

Conceptually:

    ┌──────────────┐
    │   Director   │
    └──────┬───────┘
           │
      ┌────┴────┐
      ▼         ▼
   Planner    Reviewer
      │         │
      └────┬────┘
           ▼
       Decision


Multi-agent coordination belongs to the agentic layer.

The agents may exchange reasoning state and evaluation results through
the LangGraph state/graph.

Actual infrastructure execution remains outside the agents.

---

# What LangGraph must NOT own

LangGraph must not become the durable execution engine.

It must not own:

- durable workflow lifecycle
- infrastructure retry policy
- activity scheduling
- long-running infrastructure waits
- worker recovery
- infrastructure timeouts
- human approval persistence
- direct infrastructure subprocess execution
- duplicate paid-generation prevention

Those responsibilities belong to Temporal and the execution layer.

---

# Temporal ↔ LangGraph Boundary

The boundary is:

    ┌─────────────────────────────────────┐
    │             LangGraph               │
    │                                     │
    │  Agent State                         │
    │  Reasoning Flow                      │
    │  Tool Selection                      │
    │  Conditional Branches                │
    │  Agent Loops                         │
    │  Evaluation                          │
    │  Multi-Agent Coordination            │
    └──────────────────┬──────────────────┘
                       │
                       │ execution intent
                       ▼
    ┌─────────────────────────────────────┐
    │              Temporal                │
    │                                     │
    │  Workflow State                      │
    │  Retries                             │
    │  Timeouts                            │
    │  Human Waits                         │
    │  Workflow Lifecycle                  │
    │  Activity Execution                  │
    │  Recovery                            │
    └──────────────────┬──────────────────┘
                       │
                       ▼
    ┌─────────────────────────────────────┐
    │               Workers                │
    │                                     │
    │  Blender / ComfyUI / TTS / QA       │
    └─────────────────────────────────────┘


# Critical Boundary Rule

LangGraph decides:

    "What should happen?"

Temporal decides:

    "How should that work execute durably?"

Workers perform:

    "The actual operation."


# Agent-to-Temporal Interaction

The expected interaction is:

    User / Event
        ↓
    LangGraph
        ↓
    Reason
        ↓
    Select capability
        ↓
    Create typed execution intent
        ↓
    Temporal workflow/activity
        ↓
    Worker execution
        ↓
    Result / Event
        ↓
    LangGraph
        ↓
    Evaluate result
        ↓
    Continue / Finish / Repair


LangGraph may receive the result of durable execution and reason about
what should happen next.

---

# Long-Running Work

LangGraph must not remain active simply waiting for infrastructure.

For example:

    Generate Video
         ↓
    Temporal starts activity
         ↓
    Worker performs generation
         ↓
    Temporal waits durably
         ↓
    Worker/result becomes available
         ↓
    LangGraph resumes when reasoning is required


This prevents the agent process from becoming responsible for durable
waiting.

---

# Human Decision Boundary

When a human decision is required:

    LangGraph
       ↓
    determine that approval is required
       ↓
    execution intent / workflow action
       ↓
    Temporal
       ↓
    durable human wait
       ↓
    human decision
       ↓
    Temporal resumes
       ↓
    LangGraph reasons about the result


The agent does not need to remain alive while waiting for the human.

---

# Error Boundary

Agent reasoning errors and infrastructure execution failures are different.

### Agentic reasoning failure

    LangGraph
       ↓
    invalid decision / reasoning failure
       ↓
    agent-level handling

### Infrastructure failure

    Worker
       ↓
    Activity failure
       ↓
    Temporal retry / timeout / escalation


LangGraph may subsequently evaluate the resulting state and determine
what should happen next.

---

# Canonical Hybrid Rule

The Solunex architecture is:

    LangGraph
        =
    THINK / PLAN / DECIDE / EVALUATE / ROUTE

    Temporal
        =
    EXECUTE / WAIT / RETRY / RECOVER / DURABILITY

    Workers
        =
    PERFORM THE ACTUAL WORK


# Critical Invariant

LangGraph is the authority for agentic reasoning.

Temporal is the authority for durable execution.

Neither layer should absorb the responsibilities of the other.

Therefore:

    Agent reasoning
          ↓
    LangGraph
          ↓
    Typed execution intent
          ↓
    Temporal
          ↓
    Activity
          ↓
    Worker
          ↓
    Result
          ↓
    LangGraph evaluation


# Design Principle

Keep the agentic and execution layers independently understandable.

LangGraph answers:

    "What should happen next?"

Temporal answers:

    "How do we make that happen reliably over time?"

Workers answer:

    "How do we perform the operation?"

This separation allows Solunex to combine agentic intelligence with
durable, recoverable execution without turning the LLM into the workflow
engine.
