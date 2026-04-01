# Multi-Agent Reset Plan

## Brutally Honest Gap Analysis

This repository is not currently a true multi-agent project-management system.

What it is today:
- A FastAPI backend with CRUD routes for projects, tasks, employees, blockers, meetings, and decisions
- A React dashboard for login, admin views, and a demo console
- A centralized `AutoPMService` that executes workflow logic directly
- A heuristic `AssignmentEngine` for staffing
- A thin optional `LLMService` for intake parsing and text generation
- A simulation flow that moves tasks through fake execution states

What it is not today:
- A system of independent specialized agents with explicit roles and handoffs
- A planner/executor/reviewer loop
- A sequential and parallel orchestration engine
- A shared agent memory model per workflow
- A confidence-based escalation model between agents and humans
- A real event-driven loop where agents consume and publish workflow state

## Current Architectural Mismatch

Current shape:

```text
UI -> API route -> service class -> DB
```

Desired shape:

```text
UI/API -> Orchestrator -> specialized agents -> shared workflow context -> DB
                         |                |
                         |                +-> publish decisions, risks, tasks, escalations
                         +-> run stages sequentially or in parallel
```

The most important problem is that the current system has "automation" but not "agents".
The intelligence is centralized inside service classes instead of distributed across agent roles.

## Target System

The intended platform should look more like this:

```text
Client Request
  |
  v
Intake Agent
  |
  v
Planning Agent
  |
  +----------------------+----------------------+
  |                      |                      |
  v                      v                      v
Staffing Agent       Risk Agent          Communication Agent
  |                      |                      |
  +----------+-----------+-----------+----------+
             |                       |
             v                       v
      Execution Coordinator Agent    Human Escalation Agent
             |
             v
      Review / Rebalance Loop
```

## Recommended Agent Roles

1. `IntakeAgent`
- Converts raw client/admin request into a structured brief
- Extracts goals, scope, constraints, success criteria

2. `PlanningAgent`
- Builds milestones, tasks, dependencies, and execution stages
- Produces a work graph instead of just a flat task list

3. `StaffingAgent`
- Recommends owners and backups using skills, availability, and load
- Produces confidence and alternatives, not just one answer

4. `RiskAgent`
- Evaluates schedule, staffing, blocker, and dependency risk
- Marks items that can continue autonomously vs those requiring review

5. `ExecutionCoordinatorAgent`
- Chooses next actions
- Triggers staffing, follow-ups, rebalancing, and status reconciliation

6. `CommunicationAgent`
- Drafts employee offers, admin digests, and client updates

7. `EscalationAgent`
- Decides when confidence is too low, risk too high, or conflicts unresolved
- Routes the smallest possible decision to a human

## Architecture Principles For The Rewrite

- The orchestrator coordinates; it should not contain all business intelligence.
- Each agent must produce structured output, confidence, reasoning, and next-step suggestions.
- Workflow state should be persisted so runs are inspectable.
- Parallel stages should be explicit. Example: planning complete, then staffing and risk can run in parallel.
- Existing services should become tools that agents can call.
- Human involvement should be an escalation path, not the default path.

## What Should Be Reused From The Current Repo

Keep and reuse:
- Auth and users
- Project, task, assignment, blocker, progress, decision, audit, and communication tables
- Assignment heuristics
- Monitoring logic
- Existing frontend shell for observability

Refactor rather than discard:
- `AutoPMService` should become a compatibility layer or tool adapter
- `LLMService` should become one tool among many
- `EventService` should evolve into workflow/agent event routing

## Step-By-Step Implementation Path

Phase 1:
- Add workflow-run persistence
- Add agent-run persistence
- Introduce explicit agent classes and a minimal orchestrator
- Keep execution synchronous but model sequential and parallel phases explicitly
- Add first operational agents: intake, planning, staffing, risk, execution coordination, communication, escalation

Phase 2:
- Persist structured planning output, staffing recommendations, and risk assessments
- Add workflow APIs
- Add frontend inspection for workflow runs and agent traces

Phase 3:
- Convert task intake and assignment to agent-driven execution
- Add confidence thresholds and escalation rules
- Add retry and rebalance loops

Phase 4:
- Introduce event-driven execution and background processing
- Enable real parallel worker execution where useful

## Definition Of Success

This repo starts matching the intended goal when:
- multiple specialized agents exist
- each agent has a clear responsibility
- the orchestrator runs them in a visible workflow
- agent outputs are persisted and inspectable
- human review happens only when the system cannot proceed safely on confidence/risk grounds
