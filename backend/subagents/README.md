# Iryax Multi-Product AI Agent Platform

A modular multi-agent platform tailored for Iryax's seven core vertical products. Built on typed Pydantic models, role-based access control (RBAC), and Human-in-the-Loop (HITL) approval gates.

---

## Supported Product Agents

The platform provides dedicated, domain-specific agents for each of Iryax's 7 products:

| Product | Package | Primary Capabilities | Guardrails & HITL Gates |
| :--- | :--- | :--- | :--- |
| **1. Recruitment** | `anycode.agents.products.recruitment` | Job creation, resume parsing, candidate scoring/matching, interview scheduling | Offer release requires human approval |
| **2. Attendance & Payroll** | `anycode.agents.products.payroll` | Shift reconciliation, overtime calculation, draft payroll run, payout calculations | Disbursement & salary transfer require human approval |
| **3. Task Management** | `anycode.agents.products.task_management` | Task decomposition, dependency mapping, bottleneck/blocker detection | Bulk task deletion requires human approval |
| **4. Medical Camps** | `anycode.agents.products.medical_camps` | Patient intake, vitals logging, clinical urgency triage (Normal/Urgent/Critical) | Bulk patient record export requires human approval |
| **5. OP Management** | `anycode.agents.products.op_management` | Doctor availability scheduling, token queue issuance, appointment booking | Schedule override requires human approval |
| **6. Coworking Space** | `anycode.agents.products.coworking` | Desk/cabin availability lookup, booking confirmation, cancellation | Refund issuance requires human approval |
| **7. Lab Management** | `anycode.agents.products.lab_management` | Diagnostic test ordering, specimen intake, abnormal result flagging | Diagnostic report release requires human approval |

---

## Architecture & Directory Structure

```text
src/anycode/
├── __init__.py
└── agents/
    ├── __init__.py
    └── products/
        ├── __init__.py
        ├── base_agent.py          # Abstract ProductAgent base class with RBAC validation
        ├── registry.py            # Central registry & product agent discovery
        ├── shared_schemas.py      # Common schemas (UserRole, ActionContext, ApprovalStatus)
        ├── shared_policies.py     # Base security, RBAC matrices, and HITL gate policies
        ├── shared_services.py     # Shared notification, logging, and audit services
        ├── shared_tools.py        # Generic shared utility tools
        ├── prompts/
        │   ├── system.md          # Global multi-agent platform system prompt
        │   └── orchestrator.md    # Multi-product routing and coordination prompt
        │
        ├── recruitment/           # 1. Recruitment Agent Package
        │   ├── agent.py           # Concrete agent implementation
        │   ├── config.py          # Domain configuration
        │   ├── manifest.py        # Metadata manifest & tool definitions
        │   ├── policies.py        # Domain-specific RBAC & HITL policies
        │   ├── prompts.md         # Domain prompts
        │   ├── schemas.py         # Domain Pydantic models
        │   ├── services.py        # Domain business logic services
        │   ├── tools.py           # Registered tool functions
        │   ├── workflows.py       # Multi-step business workflows
        │   ├── tests.py           # Product test suite
        │   └── __init__.py
        │
        ├── payroll/               # 2. Attendance & Payroll Agent Package
        ├── task_management/       # 3. Task Management Agent Package
        ├── medical_camps/         # 4. Medical Camps Agent Package
        ├── op_management/         # 5. Outpatient Management Agent Package
        ├── coworking/             # 6. Coworking Space Agent Package
        └── lab_management/        # 7. Diagnostic Lab Management Agent Package
```

---

## Quickstart

### 1. Register & Discover Agents

```python
from anycode.agents.products.registry import get_agent, list_agents
from anycode.agents.products.shared_schemas import ActionContext, UserRole

# List all 7 registered product agents
agents = list_agents()
print(agents)
# ['recruitment', 'payroll', 'task_management', 'medical_camps', 'op_management', 'coworking', 'lab_management']

# Instantiate the Recruitment agent
agent = get_agent("recruitment")
print(agent.manifest.name)  # "Iryax Recruitment Agent"
```

### 2. Invoke Workflows with RBAC Context

```python
import asyncio
from anycode.agents.products.registry import get_agent
from anycode.agents.products.shared_schemas import ActionContext, UserRole

async def main():
    agent = get_agent("recruitment")
    context = ActionContext(
        user_id="user_123",
        role=UserRole.ADMIN,
        product="recruitment",
        action="parse_resume"
    )

    resume_text = "Experienced Senior Python Engineer with FastAPI and PyTorch expertise."
    result = await agent.run_workflow(
        "parse_resume",
        context=context,
        resume_id="res_001",
        content=resume_text
    )
    print(result)

asyncio.run(main())
```

---

## Running Tests

Run the full product agent test suite (40 tests across all 7 products) with `pytest`:

```bash
# From the repository root:
python -m pytest -v
```
