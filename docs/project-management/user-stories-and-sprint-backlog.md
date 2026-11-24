# Sprint Planning & User Stories Backlog

## Overview
This document records the systematic sprint planning, user story decomposition, and agile execution for the **Intelligent Bug Diagnosis Platform with Fix Recommendation Assistance** (Infosys Springboard Virtual Internship).

All user stories follow standard Agile/Scrum conventions, prioritized via the **MoSCoW** (Must Have, Should Have, Could Have, Won't Have) framework, and mapped to specific engineering roles.

---

## 1. Product Backlog & User Stories

| Planned Sprint | Actual Sprint | US ID | User Story Description | MoSCoW | Dependency | Assignee | Status |
|:---:|:---:|:---:|:---|:---:|:---:|:---|:---:|
| **Sprint 1** | Sprint 1 | **US-01** | As a developer, I want the Triage Agent to classify each submitted bug as Critical, High, Medium, or Low severity so that I can quickly judge how serious it is. | Must Have | None | Kolluru Rithvik (AI/ML Developer) | **Completed** |
| **Sprint 1** | Sprint 1 | **US-02** | As a developer, I want the Triage Agent to assign a priority based on the impact and urgency of the bug so that I know what to fix first. | Must Have | US-01 | Kolluru Rithvik (AI/ML Developer) | **Completed** |
| **Sprint 1** | Sprint 1 | **US-03** | As a developer, I want the Triage Agent to identify the affected component/module from the bug description and technical information so that I know where to start investigating. | Must Have | US-01 | Kolluru Rithvik (AI/ML Developer) | **Completed** |
| **Sprint 1** | Sprint 1 | **US-04** | As a developer, I want a confidence score and short reasoning in a consistent structured output so that I can trust and reuse the triage result. | Should Have | US-01, US-03 | Kolluru Rithvik (Backend Developer) | **Completed** |
| **Sprint 2** | Sprint 2 | **US-05** | As a developer, I want the Log Analysis Agent to identify the exception type and extract the error message from stack traces and logs so that I can understand the failure quickly. | Must Have | None | Kolluru Rithvik (AI/ML Developer) | **Completed** |
| **Sprint 2** | Sprint 2 | **US-06** | As a developer, I want the agent to identify the failure point (file, class, method, line number) and the probable affected code path so that I can locate the faulty code. | Must Have | US-05 | Kolluru Rithvik (AI/ML Developer) | **Completed** |
| **Sprint 2** | Sprint 2 | **US-07** | As a developer, I want the agent to handle different stack-trace and log formats so that bugs from any language or tool can be analyzed. | Should Have | US-05 | Kolluru Rithvik (Backend Developer) | **Completed** |
| **Sprint 2** | Sprint 2 | **US-08** | As a developer, I want a structured output with exception type, error message, failure point, code path, and confidence score so that other agents can consume it. | Must Have | US-06 | Kolluru Rithvik (Backend Developer) | **Completed** |
| **Sprint 3** | Sprint 3 | **US-09** | As a developer, I want the Triage and Log Analysis agents to run automatically when a bug is submitted so that analysis starts without manual effort. | Must Have | US-04, US-08 | Kolluru Rithvik (Backend Developer) | **Completed** |
| **Sprint 3** | Sprint 3 | **US-10** | As a developer, I want the bug description, stack trace, and logs routed to the right agents and their outputs combined into one structured bug context so that the analysis is consistent. | Must Have | US-09 | Kolluru Rithvik (Backend Developer) | **Completed** |
| **Sprint 3** | Sprint 3 | **US-11** | As a developer, I want error handling for missing logs, invalid input, agent failures, and incomplete analysis so that the system stays reliable. | Should Have | US-09 | Kolluru Rithvik (Backend Developer) | **Completed** |
| **Sprint 3** | Sprint 3 | **US-12** | As a developer, I want the combined agent outputs to be passed as context to downstream agents so that Milestone 3 agents can build on them. | Must Have | US-10 | Kolluru Rithvik (AI/ML Developer) | **Completed** |
| **Sprint 4** | Sprint 4 | **US-13** | As a developer, I want a test set built from the seeded defect dataset (description-only, with stack trace, logs-only, messy logs) so that the agents are tested on varied inputs. | Must Have | US-12 | Kolluru Rithvik (QA Engineer) | **Completed** |
| **Sprint 4** | Sprint 4 | **US-14** | As a developer, I want to measure Triage Agent accuracy for severity, priority, and affected component so that I know how reliable it is. | Must Have | US-13 | Kolluru Rithvik (QA Engineer) | **Completed** |
| **Sprint 4** | Sprint 4 | **US-15** | As a developer, I want to measure Log Analysis Agent accuracy for exception type, failure point, and code path so that I know how reliable it is. | Must Have | US-13 | Kolluru Rithvik (QA Engineer) | **Completed** |
| **Sprint 4** | Sprint 4 | **US-16** | As a developer, I want incorrect predictions recorded and analyzed, and prompts, rules, and parsing improved so that agent accuracy increases. | Should Have | US-14, US-15 | Kolluru Rithvik (AI/ML Developer) | **Completed** |

---

## 2. Sprint Breakdown & Scope

### Sprint 1: Triage Agent & Classification Foundation
- **Goal**: Implement first-level defect triage: severity categorization (`Critical`, `High`, `Medium`, `Low`), priority assignment (`P1` to `P4`), and affected architectural component identification.
- **Key Deliverables**:
  - `TriageAgent` implementation with dual-engine (Rule-based heuristic baseline + LLM reasoning).
  - Vocabulary mapping and component taxonomies (`backend/app/agents/triage/`).
  - Unit tests for severity, priority, and component scoring.

### Sprint 2: Log Analysis Agent & 9 Stack-Trace Parsers
- **Goal**: Extract deterministic error signals from unstructured logs and multi-language stack traces.
- **Key Deliverables**:
  - 9 format parsers: Java, Python, JS V8, JS Firefox, Go Panic, .NET, C/C++ GDB, Android Logcat, Generic Logs.
  - Granular failure point isolation (file, class, method, line) and reconstructed chronological call paths.
  - 10 fixtures with ground-truth expected JSONs.

### Sprint 3: Multi-Agent Orchestration & BugContext Contract
- **Goal**: Connect submission module to automated agent pipelines via LangGraph.
- **Key Deliverables**:
  - LangGraph `StateGraph` dispatching Triage and Log Analysis concurrently.
  - Relational persistence in SQLite (`bug_analyses` and `agent_runs` tables).
  - Common `BugContext` contract ready for downstream consumption.
  - Frontend `AnalysisPanel` with real-time status and fallback resilience.

### Sprint 4: Accuracy Validation, Test Harness & Defect Fixing
- **Goal**: Validate agent accuracy across seeded defect datasets and establish continuous refinement loop.
- **Key Deliverables**:
  - Automated validation harness (`app/agents/validation/runner.py`).
  - 174 passing automated tests in CI/CD pipeline.
  - 12 development defects diagnosed, resolved, and documented in defect log.
