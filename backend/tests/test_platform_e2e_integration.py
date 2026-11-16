"""End-to-End Platform Integration & Subagent Connection Tests.

Verifies:
1. Registration of all 7 specialized product agents.
2. Natural-language intent classification & multi-agent routing.
3. Subagent direct workflow execution.
4. Real scraped data integrity (Timely Health employee roster & payroll).
5. Human-in-the-Loop (HITL) governance gate enforcement.
6. HITL approval decision lifecycle (Approve / Reject).
7. FastAPI HTTP API contract (/health, /approvals, /agents/execute).
8. Boundary enforcement & unknown agent rejection.
"""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from api import app
from orchestrator import orchestrator
from anycode.agents.products.shared_schemas import (
    ApprovalStatus,
    ExecutionStatus,
    ProductId,
    Role,
)


class TestPlatformE2EIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from api import get_current_principal, AuthenticatedPrincipal

        app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
            user_id="test-user",
            tenant_id="test-tenant",
            role="tenant_admin",
        )

        cls.client = TestClient(app)
        cls.expected_products = [
            ProductId.RECRUITMENT.value,
            ProductId.PAYROLL.value,
            ProductId.TASK_MANAGEMENT.value,
            ProductId.MEDICAL_CAMPS.value,
            ProductId.OP_MANAGEMENT.value,
            ProductId.COWORKING.value,
            ProductId.LAB_MANAGEMENT.value,
        ]

    def test_01_all_seven_agents_registered(self):
        """Case 1: All 7 specialized product subagents are registered and initialized."""
        subagents = orchestrator.list_subagents()
        registered_ids = [a["product_id"] for a in subagents]
        for prod_id in self.expected_products:
            self.assertIn(prod_id, registered_ids, f"Agent {prod_id} missing from orchestrator")
        self.assertEqual(len(registered_ids), 7)

    def test_02_query_classification_routing(self):
        """Case 2: Natural-language queries route to the appropriate domain agent."""
        routing_fixtures = [
            ("Review candidate resumes for senior developer job posting", ProductId.RECRUITMENT),
            ("Process attendance deductions and calculate employee salary", ProductId.PAYROLL),
            ("Create agile sprint backlog task for engineering team", ProductId.TASK_MANAGEMENT),
            ("Schedule rural medical camp screening and register participants", ProductId.MEDICAL_CAMPS),
            ("Book outpatient doctor consultation and check queue appointment", ProductId.OP_MANAGEMENT),
            ("Reserve coworking hot desk and check cabin availability", ProductId.COWORKING),
            ("Enter pathology lab specimen test results for CBC sample", ProductId.LAB_MANAGEMENT),
        ]
        for query, expected_prod in routing_fixtures:
            classified_pid = orchestrator.classify_query(query)
            self.assertIsNotNone(classified_pid, f"Failed to classify: '{query}'")
            self.assertEqual(
                classified_pid,
                expected_prod,
                f"Query '{query}' routed to {classified_pid}, expected {expected_prod}",
            )

    def test_03_subagent_direct_method_execution(self):
        """Case 3: Direct execution of subagent methods executes registered domain tools."""
        res = orchestrator.execute_subagent(
            product_id="recruitment",
            query="list_candidates()",
            parameters={"intent": "list_candidates"},
        )
        self.assertEqual(res.status, ExecutionStatus.SUCCESS)
        self.assertGreater(len(res.tools_executed), 0)
        self.assertIn("Alex Johnson", res.response_text)
        self.assertIn("12 Candidates", res.response_text)

    def test_04_real_scraped_employee_data_integrity(self):
        """Case 4: Payroll subagent accesses authentic scraped TimelyHealth employee roster."""
        res = orchestrator.execute_subagent(
            product_id="payroll",
            query="run_payroll()",
            parameters={"intent": "run_payroll"},
        )
        self.assertEqual(res.status, ExecutionStatus.SUCCESS)
        # Real TimelyHealth employees scraped from https://www.timelyhealth.in/employeelist
        self.assertIn("Dara Gowthami", res.response_text)
        self.assertIn("Aarif", res.response_text)
        self.assertIn("Janapala Bharath", res.response_text)
        self.assertIn("255,000", res.response_text)

    def test_05_hitl_approval_gate_enforcement(self):
        """Case 5: High-consequence actions trigger HITL approval pause."""
        res = orchestrator.execute_subagent(
            product_id="payroll",
            query="release_payment()",
            parameters={"intent": "release_payment"},
        )
        self.assertEqual(res.status, ExecutionStatus.PENDING_APPROVAL)
        self.assertIsNotNone(res.approval_request)
        self.assertTrue(res.approval_request.approval_id.startswith("appr_"))

    def test_06_hitl_approval_lifecycle_decision(self):
        """Case 6: HITL approval can be reviewed and approved by an authorized role."""
        res = orchestrator.execute_subagent(
            product_id="recruitment",
            query="extend_offer()",
            parameters={"intent": "extend_offer"},
        )
        self.assertEqual(res.status, ExecutionStatus.PENDING_APPROVAL)
        approval_id = res.approval_request.approval_id

        # Decide approval
        decision = orchestrator.decide_approval(
            approval_id=approval_id,
            approve=True,
            reviewer_id="lead_hr_officer",
            role=Role.TENANT_ADMIN,
            reason="Offer package verified within budget",
        )
        self.assertEqual(decision["status"], "approved")
        self.assertEqual(decision["approval_id"], approval_id)

    def test_07_fastapi_http_endpoints_integration(self):
        """Case 7: FastAPI endpoints (/health, /approvals, /agents/execute) respond via HTTP."""
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json().get("status"), "ok")

        approvals = self.client.get("/approvals")
        self.assertEqual(approvals.status_code, 200)
        self.assertIn("approvals", approvals.json())

        exec_res = self.client.post(
            "/agents/execute",
            json={
                "product_id": "coworking",
                "query": "check_availability()",
                "parameters": {"intent": "check_availability"},
            },
        )
        self.assertEqual(exec_res.status_code, 200)
        data = exec_res.json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("DESK-A101", data.get("answer", ""))

    def test_08_unknown_agent_boundary_rejection(self):
        """Case 8: Requests to unregistered agents are safely rejected."""
        with self.assertRaises(ValueError):
            orchestrator.execute_subagent(
                product_id="nonexistent_product",
                query="do_something()",
                parameters={},
            )
        resp = self.client.post(
            "/agents/execute",
            json={
                "product_id": "invalid_domain",
                "query": "test()",
            },
        )
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
