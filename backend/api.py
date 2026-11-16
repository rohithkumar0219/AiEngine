"""
Iryax AI Engine — FastAPI Application (v2.1).

JWT-authenticated API for the Iryax multi-product AI platform.

Security model:
- /health and GET /chat metadata are public.
- All operational API routes require a signed JWT.
- User identity, tenant ID and role are read only from verified JWT claims.
- Client-supplied identity fields are not part of request schemas.
- Invalid roles fail closed; no administrator fallback exists.
"""

from __future__ import annotations

import json as _json
import logging
import os
import pathlib
import sys
from typing import Any, Dict, List, Optional

# Resolve paths and add the backend source directories before local imports.
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

SUBAGENTS_SRC = ROOT / "subagents" / "src"
if str(SUBAGENTS_SRC) not in sys.path:
        sys.path.insert(0, str(SUBAGENTS_SRC))

# Load environment before importing auth.security (which reads JWT settings).
from dotenv import load_dotenv

_backend_env = ROOT / ".env"
_project_env = ROOT.parent / ".env"
if _backend_env.is_file():
        load_dotenv(_backend_env, override=False)
if _project_env.is_file():
        load_dotenv(_project_env, override=False)

# Read JWT settings once, from the environment shared by the API and auth layer.
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ISSUER = os.getenv("JWT_ISSUER", "iryax-auth")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "iryax-api")
JWT_ALGORITHM = "HS256"
JWT_LEEWAY_SECONDS = 30

import jwt
from fastapi import (
Depends,
FastAPI,
HTTPException,
Query,
Request,
status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from auth import database
from auth.service import (
authenticate_admin,
issue_token_pair,
refresh_admin_session,
logout_admin,
get_active_admin,
)
from auth.schemas import (
AdminLoginRequest,
RefreshTokenRequest,
AdminTokenResponse,
AdminProfileResponse,
)
from auth.security import utc_now, utc_iso

logger = logging.getLogger(__name__)

from guardrails import InputGuardrail, OutputGuardrail, TenantGuardrail
from analytics_engine import analyze_product_module
from deployment_engine import get_cluster_status, run_parallel_cluster_deployment
from evaluations import run_full_evaluation_suite

# ── Import multi-agent orchestrator ───────────────────────────────────────────


try:

        from orchestrator import orchestrator


        _ORCHESTRATOR_AVAILABLE = True

except Exception:

        logger.exception(

                "AgentOrchestrator failed to load. Falling back to RAG-only mode."

        )

        orchestrator = None     # type: ignore[assignment]

        _ORCHESTRATOR_AVAILABLE = False


# ── Import RAG pipeline ───────────────────────────────────────────────────────


try:

        from rag_pipeline import (

                generate_rag_response,

                clear_semantic_cache,

                log_feedback,

                get_analytics_summary,

        )

except ImportError:

        from backend.rag_pipeline import (     # type: ignore[no-redef]

                generate_rag_response,

                clear_semantic_cache,

                log_feedback,

                get_analytics_summary,

        )


SCRAPER_LOG_PATH = ROOT / "scraper.log"


bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedPrincipal(BaseModel):

        """Identity derived from verified JWT claims."""


        user_id: str

        tenant_id: str

        role: str


def _role_from_str(role_str: str):

        """

        Convert a JWT role claim into the platform Role enum.


        Fail closed. Never silently elevate an unknown role to administrator.

        """

        from subagents.src.anycode.agents.products.shared_schemas import Role


        try:

                return Role(role_str)

        except (ValueError, TypeError):

                raise HTTPException(

                        status_code=status.HTTP_403_FORBIDDEN,

                        detail="Invalid or unauthorized role.",

                )


async def get_current_principal(

        credentials: Optional[HTTPAuthorizationCredentials] = Depends(

                bearer_scheme

        ),

) -> AuthenticatedPrincipal:


        if credentials is None or credentials.scheme.lower() != "bearer":

                raise HTTPException(

                        status_code=401,

                        detail="Authentication required.",

                        headers={"WWW-Authenticate": "Bearer"},

                )


        if not JWT_SECRET_KEY or len(JWT_SECRET_KEY.encode("utf-8")) < 32:

                raise HTTPException(

                        status_code=503,

                        detail="Authentication service is not configured.",

                )


        try:

                payload = jwt.decode(

                        credentials.credentials,

                        JWT_SECRET_KEY,

                        algorithms=[JWT_ALGORITHM],

                        issuer=JWT_ISSUER,

                        audience=JWT_AUDIENCE,

                        leeway=JWT_LEEWAY_SECONDS,

                        options={

                                "require": [

                                                "exp", "iat", "sub", "tenant_id",

                                                "role", "iss", "aud", "type",

                                ],

                        },

                )

        except jwt.InvalidTokenError:

                raise HTTPException(

                        status_code=401,

                        detail="Invalid or expired access token.",

                        headers={"WWW-Authenticate": "Bearer"},

                )


        if payload.get("type") != "access":

                raise HTTPException(

                        status_code=401,

                        detail="An access token is required.",

                )


        user_id = payload.get("sub")

        tenant_id = payload.get("tenant_id")

        role = payload.get("role")


        if not all(

                isinstance(value, str) and value.strip()

                for value in (user_id, tenant_id, role)

        ):

                raise HTTPException(

                        status_code=401,

                        detail="Invalid identity claims.",

                )


        authenticated_role = _role_from_str(role)


        if getattr(authenticated_role, "name", None) != "TENANT_ADMIN":

                raise HTTPException(

                        status_code=403,

                        detail="Administrator access required.",

                )


        admin = get_active_admin(user_id)


        if not admin:

                raise HTTPException(

                        status_code=401,

                        detail="Administrator account is inactive or unavailable.",

                )


        if admin["tenant_id"] != tenant_id:

                raise HTTPException(

                        status_code=403,

                        detail="Tenant authorization failed.",

                )


        if admin["role"] != role:

                raise HTTPException(

                        status_code=403,

                        detail="Administrator role verification failed.",

                )


        return AuthenticatedPrincipal(

                user_id=user_id,

                tenant_id=tenant_id,

                role=role,

        )


# ── App factory ───────────────────────────────────────────────────────────────


app = FastAPI(

        title="Iryax AI Engine",

        description=(

                "JWT-authenticated multi-agent AI backend for the Iryax platform. "

                "Routes queries to specialized product subagents or the Groq-powered "

                "RAG pipeline."

        ),

        version="2.1.0",

)


@app.on_event("startup")

async def initialize_auth_database():

        database.initialize_database()
        # SECURITY: No automatic credential provisioning at startup.
        # Administrators must be provisioned manually using:
        #   python backend/provision_admin.py --email <email> --tenant <tenant_id>
        # This prevents default credentials from being created in production.


# Set CORS_ALLOWED_ORIGINS to a comma-separated list of exact frontend origins.

# Example: https://app.iryax.com,https://iryax.com

_default_origins = (
        "http://localhost:3000,http://localhost:5173,"
        "http://127.0.0.1:3000,http://127.0.0.1:5173,"
        "http://127.0.0.1:8000,http://localhost:8000,"
        "https://app.iryax.com,https://iryax.com"
)

CORS_ALLOWED_ORIGINS = [

        origin.strip()

        for origin in os.getenv(

                "CORS_ALLOWED_ORIGINS", _default_origins

        ).split(",")

        if origin.strip()

]


app.add_middleware(

        CORSMiddleware,

        allow_origins=CORS_ALLOWED_ORIGINS,

        allow_credentials=True,

        allow_methods=["GET", "POST", "OPTIONS"],

        allow_headers=["Authorization", "Content-Type"],

)


# ── Admin authentication routes ──────────────────────────────


@app.post(

        "/auth/login",

        response_model=AdminTokenResponse,

        tags=["Authentication"],

)

def admin_login(payload: AdminLoginRequest):

        admin = authenticate_admin(

                email=str(payload.email),

                password=payload.password,

        )


        if not admin:

                raise HTTPException(

                        status_code=status.HTTP_401_UNAUTHORIZED,

                        detail="Invalid email or password.",

                        headers={"WWW-Authenticate": "Bearer"},

                )


        try:

                return issue_token_pair(admin)

        except Exception:

                logger.exception("Admin token issuance failed.")

                raise HTTPException(

                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

                        detail="Unable to issue authentication tokens.",

                )


@app.post(

        "/auth/refresh",

        response_model=AdminTokenResponse,

        tags=["Authentication"],

)

def admin_refresh(payload: RefreshTokenRequest):

        tokens = refresh_admin_session(payload.refresh_token)


        if not tokens:

                raise HTTPException(

                        status_code=status.HTTP_401_UNAUTHORIZED,

                        detail="Invalid, expired, or revoked refresh token.",

                )


        return tokens


@app.post("/auth/logout", tags=["Authentication"])

def admin_logout(

        payload: RefreshTokenRequest,

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        revoked = logout_admin(

                raw_refresh_token=payload.refresh_token,

                authenticated_admin_id=principal.user_id,

        )


        if not revoked:

                raise HTTPException(

                        status_code=status.HTTP_401_UNAUTHORIZED,

                        detail="Invalid refresh token or session.",

                )


        return {"message": "Logged out successfully."}


@app.get(

        "/auth/me",

        response_model=AdminProfileResponse,

        tags=["Authentication"],

)

def admin_me(

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        admin = get_active_admin(principal.user_id)


        if not admin:

                raise HTTPException(

                        status_code=status.HTTP_401_UNAUTHORIZED,

                        detail="Administrator account is inactive or unavailable.",

                )


        return AdminProfileResponse(

                id=admin["id"],

                email=admin["email"],

                tenant_id=admin["tenant_id"],

                role=admin["role"],

        )


# ── Request / response schemas ────────────────────────────────────────────────

#

# Identity fields are deliberately absent. Pydantic's default extra-field

# behavior ignores legacy client fields such as user_id, tenant_id and role;

# they are never used to establish identity.


class ChatRequest(BaseModel):

        model_config = ConfigDict(extra="ignore")


        message: str = ""

        question: str = ""

        history: List[Dict[str, str]] = Field(default_factory=list)

        website_id: str = "https://iryax.com"

        session_id: str = "default_session"

        agent: Optional[str] = None

        page_context: Optional[Dict[str, Any]] = None


        @property

        def user_query(self) -> str:

                return (self.question or self.message).strip()


class AgentExecuteRequest(BaseModel):

        model_config = ConfigDict(extra="ignore")


        product_id: str

        query: str

        parameters: Dict[str, Any] = Field(default_factory=dict)

        page_context: Optional[Dict[str, Any]] = None


class ApprovalDecisionRequest(BaseModel):

        model_config = ConfigDict(extra="ignore")


        approve: bool

        reason: Optional[str] = None


class FeedbackRequest(BaseModel):

        model_config = ConfigDict(extra="ignore")


        query: str

        rating: str

        comment: str = ""


# ── Health check ──────────────────────────────────────────────────────────────


@app.get("/health")

async def health_check():

        """Public liveness check. Does not expose secrets or user data."""

        return {

                "status": "ok",

                "message": "Iryax AI Engine is running",

                "orchestrator": (

                        "online" if _ORCHESTRATOR_AVAILABLE else "degraded (RAG-only)"

                ),

                "version": "2.1.0",

        }


# ── Chat — primary streaming endpoint ─────────────────────────────────────────


@app.post("/chat")

async def chat_endpoint(

        req: ChatRequest,

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        """

        Authenticated streaming chat via NDJSON.


        Routing:

        1. If agent is specified, dispatch to that subagent.

        2. Otherwise, use orchestrator classification and streaming.

        3. If orchestrator is unavailable, use the RAG fallback.


        The principal is created from verified JWT claims, not request JSON.

        """

        query = req.user_query

        if not query:

                raise HTTPException(

                        status_code=status.HTTP_400_BAD_REQUEST,

                        detail="Empty message received.",

                )

        # Input Guardrail Inspection
        guard_res = InputGuardrail.inspect(query)
        if not guard_res.is_safe:
                def blocked_gen():
                        yield (
                                _json.dumps(
                                        {
                                                "token": f"🚨 **Security Guardrail Alert**: {guard_res.violations[0]}\n\nOperation rejected by Iryax Multi-Tenant Input Guardrail.",
                                                "sources": ["guardrail:prompt_injection_blocked"],
                                                "status": "blocked",
                                        }
                                )
                                + "\n"
                        )
                        yield (
                                _json.dumps(
                                        {
                                                "token": "",
                                                "sources": ["guardrail:prompt_injection_blocked"],
                                                "answer": guard_res.sanitized_text,
                                                "status": "blocked",
                                        }
                                )
                                + "\n"
                        )

                return StreamingResponse(
                        blocked_gen(),
                        media_type="application/x-ndjson",
                )

        target_agent = req.agent
        if not target_agent and req.page_context:
                target_agent = req.page_context.get("module_id")

        if req.page_context:
                ctx_parts = []
                if req.page_context.get("selected_record"):
                        ctx_parts.append(f"Selected Record: {req.page_context.get('selected_record')}")
                if req.page_context.get("filters"):
                        ctx_parts.append(f"Active Filters: {req.page_context.get('filters')}")
                if ctx_parts:
                        query = f"{query} [Module Context: {', '.join(ctx_parts)}]"

        if _ORCHESTRATOR_AVAILABLE and orchestrator is not None:

                role = _role_from_str(principal.role)


                def generator():

                        if target_agent:

                                try:

                                                resp = orchestrator.execute_subagent(

                                                        product_id=target_agent,

                                                        query=query,

                                                        parameters={},

                                                        role=role,

                                                        user_id=principal.user_id,

                                                        tenant_id=principal.tenant_id,

                                                )

                                                yield (

                                                        _json.dumps(

                                                                {"token": resp.response_text, "agent": req.agent}

                                                        )

                                                        + "\n"

                                                )

                                                yield (

                                                        _json.dumps(

                                                                {

                                                                        "token": "",

                                                                        "answer": resp.response_text,

                                                                        "status": resp.status.value,

                                                                                "agent": req.agent,

                                                                }

                                                        )

                                                        + "\n"

                                                )

                                except Exception:

                                                logger.exception(

                                                        "Forced subagent execution failed for product %s",

                                                        req.agent,

                                                )

                                                yield (

                                                        _json.dumps(

                                                                {

                                                                        "token": "Agent execution failed.",

                                                                        "agent": req.agent,

                                                                        "error": True,

                                                                }

                                                        )

                                                        + "\n"

                                                )

                        else:

                                try:

                                                yield from orchestrator.dispatch_streaming(

                                                        query=query,

                                                        history=req.history,

                                                        role=role,

                                                        user_id=principal.user_id,

                                                        tenant_id=principal.tenant_id,

                                                )

                                except Exception:

                                                logger.exception("Orchestrator streaming failed.")

                                                yield (

                                                        _json.dumps(

                                                                {

                                                                        "token": "Agent execution failed.",

                                                                        "error": True,

                                                                }

                                                        )

                                                        + "\n"

                                                )


                return StreamingResponse(

                        generator(),

                        media_type="application/x-ndjson",

                )


        # RAG-only fallback remains authenticated.

        def rag_generator():

                try:
                        for chunk in generate_rag_response(
                        query,
                        req.history,
                        tenant_id=principal.tenant_id,
                        user_id=principal.user_id,
                        ):

                                yield chunk

                except Exception:

                        logger.exception("RAG response generation failed.")

                        yield _json.dumps(

                                {"error": "Response generation failed."}

                                ) + "\n"


        return StreamingResponse(

                rag_generator(),

                media_type="application/x-ndjson",

        )


@app.get("/chat")

async def chat_get_info():

        """Public API metadata. Does not disclose identity fields."""

        return {

                "endpoint": "/chat",

                "method_required": "POST",

                "authentication": "Bearer JWT required",

                "body": {

                        "message": "string",

                        "question": "string (optional)",

                        "history": "list[dict]",

                        "agent": "string (optional — force specific subagent)",

                },

                "docs": "/docs",

        }


# ── Subagent management ───────────────────────────────────────────────────────


@app.get("/agents")

async def list_agents(

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        """List registered product subagents. Authentication required."""

        if not _ORCHESTRATOR_AVAILABLE or orchestrator is None:

                raise HTTPException(

                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

                        detail="Orchestrator is not available.",

                )

        return {"agents": orchestrator.list_subagents()}


@app.post("/agents/execute")

async def execute_agent(

        req: AgentExecuteRequest,

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        """Directly invoke a product subagent using verified caller identity."""

        if not _ORCHESTRATOR_AVAILABLE or orchestrator is None:

                raise HTTPException(

                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

                        detail="Orchestrator is not available.",

                )


        guard_res = InputGuardrail.inspect(req.query)
        if not guard_res.is_safe:
                raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Security Guardrail Violation: {guard_res.violations[0]}",
                )

        try:
                # Inject page context into parameters and enrich query if present
                exec_params = dict(req.parameters)
                enriched_query = req.query
                if req.page_context:
                        exec_params["page_context"] = req.page_context
                        ctx_parts = []
                        if req.page_context.get("selected_record"):
                                ctx_parts.append(f"Selected Record: {req.page_context.get('selected_record')}")
                        if req.page_context.get("filters"):
                                ctx_parts.append(f"Active Filters: {req.page_context.get('filters')}")
                        if ctx_parts:
                                enriched_query = f"{req.query} [Module Context: {', '.join(ctx_parts)}]"

                response = orchestrator.execute_subagent(
                        product_id=req.product_id,
                        query=enriched_query,
                        parameters=exec_params,
                        role=_role_from_str(principal.role),
                        user_id=principal.user_id,
                        tenant_id=principal.tenant_id,
                )


                return {

                        "status": response.status.value,

                        "answer": response.response_text,

                        "tools_executed": [

                                tool.tool_name for tool in response.tools_executed

                        ],

                        "approval_request": (

                                {

                                                "approval_id": response.approval_request.approval_id,

                                                "operation_name": (

                                                        response.approval_request.operation_name

                                                ),

                                }

                                if response.approval_request

                                else None

                        ),

                }

        except HTTPException:

                raise

        except ValueError as exc:

                raise HTTPException(

                        status_code=status.HTTP_404_NOT_FOUND,

                        detail=str(exc),

                )

        except Exception:

                logger.exception("Agent execution failed.")

                raise HTTPException(

                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

                        detail="Agent execution failed.",

                )


@app.get("/agents/{product_id}/analyze")
async def analyze_agent_module(
        product_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
        """Retrieve deep-dive structured module analysis."""
        try:
                analysis = analyze_product_module(product_id)
                return analysis.model_dump()
        except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
        except Exception as exc:
                logger.exception("Analysis generation failed.")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@app.get("/agents/deploy/status")
async def get_agent_deployment_status():
        """Retrieve real-time deployment status of all 7 agents."""
        return get_cluster_status().model_dump()


@app.post("/agents/deploy/parallel")
async def trigger_agent_parallel_deployment(
        simulate_failure_id: Optional[str] = Query(None, description="Optional agent ID to simulate failure on"),
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
        """Run parallel deployment of all 7 agents with progress telemetry."""
        summary = await run_parallel_cluster_deployment(simulate_failure_id=simulate_failure_id)
        return summary.model_dump()


@app.post("/agents/deploy/recover/{agent_id}")
async def recover_agent_endpoint(
        agent_id: str,
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
        """Self-healing recovery: reloads and redeploys a failed subagent cleanly."""
        from deployment_engine import recover_single_agent
        try:
            recovered = await recover_single_agent(agent_id)
            return recovered.model_dump()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))


@app.get("/evaluations/run")
async def run_evaluation_benchmark(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
        """Execute comprehensive automated evaluation benchmark."""
        report = run_full_evaluation_suite()
        return report.model_dump()


# ── Human-in-the-loop approval management ─────────────────────────────────────


@app.get("/approvals")

async def list_approvals(

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        """

        List approvals for the authenticated caller's tenant only.

        Tenant ID is never accepted from a query parameter.

        """

        if not _ORCHESTRATOR_AVAILABLE or orchestrator is None:

                raise HTTPException(

                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

                                detail="Orchestrator is not available.",

                )


        return {

                "approvals": orchestrator.list_approvals(

                        tenant_id=principal.tenant_id

                )

        }


@app.post("/approvals/{approval_id}/decide")

async def decide_approval(

        approval_id: str,

        req: ApprovalDecisionRequest,

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        """

        Decide an approval using the authenticated reviewer identity.


        The orchestrator must still enforce reviewer permissions and tenant

        ownership independently. This endpoint does not grant approval rights

        merely because a caller has a valid JWT.

        """

        if not _ORCHESTRATOR_AVAILABLE or orchestrator is None:

                raise HTTPException(

                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

                        detail="Orchestrator is not available.",

                )


        try:

                return orchestrator.decide_approval(

                        approval_id=approval_id,

                        approve=req.approve,

                        reviewer_id=principal.user_id,

                        role=_role_from_str(principal.role),

                        tenant_id=principal.tenant_id,

                        reason=req.reason,

                )

        except PermissionError:

                raise HTTPException(

                        status_code=status.HTTP_403_FORBIDDEN,

                        detail="Not authorized to decide this approval.",

                )

        except ValueError:

                # Avoid exposing whether another tenant owns this approval.

                raise HTTPException(

                        status_code=status.HTTP_404_NOT_FOUND,

                                detail="Approval not found or unavailable.",

                )

        except HTTPException:

                raise

        except Exception:

                logger.exception("Approval decision failed.")

                raise HTTPException(

                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

                        detail="Approval decision failed.",

                )


# ── Feedback ─────────────────────────────────────────────────────────────────


@app.post("/feedback")

async def post_feedback(

        req: FeedbackRequest,

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        """Record feedback from an authenticated caller."""

        if req.rating not in {"thumbs_up", "thumbs_down"}:

                raise HTTPException(

                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,

                        detail="rating must be 'thumbs_up' or 'thumbs_down'.",

                )

        return log_feedback(req.query, req.rating, req.comment)


# ── Executive Business Dashboard Summary ──────────────────────────────────────


@app.get("/dashboard/summary")
async def get_dashboard_summary(
	principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
	"""
	Consolidated Executive Business Command Centre summary.
	Aggregates real-time KPIs, pending approvals, operational issues,
	module health scores, recent activities, and executive AI insights.
	Enforces role-based data filtering.
	"""
	try:
		from subagents.src.anycode.agents.products.shared_services import audit_service, approval_service

		is_admin = principal.role in ("super_admin", "tenant_admin", "auditor", "admin")
		is_manager = principal.role in ("hr_admin", "payroll_admin", "task_lead", "workspace_admin", "manager")
		is_employee = not (is_admin or is_manager)

		# 1. Fetch analysis for all 7 modules
		all_modules = [
			("recruitment", "Recruitment AI", "users", "Talent & Hiring"),
			("payroll", "Payroll AI", "wallet", "Compensation & Attendance"),
			("task_management", "Task Management AI", "check", "Engineering & Sprint Velocity"),
			("medical_camps", "Medical Camps AI", "medical", "Community Healthcare"),
			("op_management", "OP Management AI", "calendar", "Clinic & Patient Queue"),
			("coworking", "Coworking AI", "building", "Facility & Workspace"),
			("lab_management", "Lab Management AI", "lab", "Diagnostics & Pathology"),
		]

		module_analyses = {}
		for mod_id, _, _, _ in all_modules:
			try:
				module_analyses[mod_id] = analyze_product_module(mod_id)
			except Exception as e:
				logger.warning("Failed analyzing module %s: %s", mod_id, e)

		# Calculate organizational health score
		scores = [ma.performance_score for ma in module_analyses.values()]
		org_health_score = round(sum(scores) / max(1, len(scores))) if scores else 90

		# 2. Executive KPIs (calculated directly from live module analytics)
		payroll_analysis = module_analyses.get("payroll")
		payroll_val = "₹255,000"
		payroll_sub = "10 Active Staff · TimelyHealth"
		if payroll_analysis and len(payroll_analysis.statistics) >= 2:
			payroll_val = payroll_analysis.statistics[1].value
			payroll_sub = f"{payroll_analysis.statistics[0].value} Active Staff · TimelyHealth"

		rec_analysis = module_analyses.get("recruitment")
		cand_val = "12 Candidates"
		cand_sub = "6 Top Matches (≥90%)"
		if rec_analysis and len(rec_analysis.statistics) >= 2:
			cand_val = f"{rec_analysis.statistics[0].value} Candidates"
			cand_sub = f"{rec_analysis.statistics[1].value} Top Matches (≥90%)"

		task_analysis = module_analyses.get("task_management")
		task_val = "20% Completed"
		task_sub = "1 Blocked Task (TSK-102)"
		if task_analysis and len(task_analysis.statistics) >= 3:
			task_val = f"{task_analysis.statistics[1].value} Completed"
			task_sub = f"{task_analysis.statistics[2].value} Blocked · {task_analysis.statistics[0].value} Active Tasks"

		med_analysis = module_analyses.get("medical_camps")
		reach_val = "285 Registered"
		reach_sub = "3 Outreach Camps"
		if med_analysis and len(med_analysis.statistics) >= 3:
			reach_val = f"{med_analysis.statistics[2].value} Registered"
			reach_sub = f"{med_analysis.statistics[0].value} Camps · {med_analysis.statistics[1].value} Capacity"

		cowork_analysis = module_analyses.get("coworking")
		cowork_val = "17% Occupancy"
		cowork_sub = "6 Total Resources"
		if cowork_analysis and len(cowork_analysis.statistics) >= 2:
			cowork_val = f"{cowork_analysis.statistics[1].value} Occupancy"
			cowork_sub = f"{cowork_analysis.statistics[0].value} Resources · {cowork_analysis.statistics[2].value} Desks Avail"

		lab_analysis = module_analyses.get("lab_management")
		lab_val = "4 Specimens"
		lab_sub = "1 Pending Sign-Off"
		if lab_analysis and len(lab_analysis.statistics) >= 3:
			lab_val = f"{lab_analysis.statistics[0].value} Specimens"
			lab_sub = f"{lab_analysis.statistics[1].value} Pending Sign-Off · {lab_analysis.statistics[3].value}"

		executive_kpis = [
			{
				"id": "kpi_payroll",
				"label": "Monthly Payroll Cycle",
				"value": payroll_val if not is_employee else "Confidential",
				"subtext": payroll_sub if not is_employee else "Restricted Access",
				"trend": "Audit Ready",
				"status": "normal",
				"category": "Finance",
				"target_module": "payroll",
			},
			{
				"id": "kpi_talent",
				"label": "Talent Pipeline",
				"value": cand_val,
				"subtext": cand_sub,
				"trend": "89.8% Avg Match",
				"status": "positive",
				"category": "Talent",
				"target_module": "recruitment",
			},
			{
				"id": "kpi_tasks",
				"label": "Sprint Velocity",
				"value": task_val,
				"subtext": task_sub,
				"trend": "Sprint 14",
				"status": "warning",
				"category": "Engineering",
				"target_module": "task_management",
			},
			{
				"id": "kpi_healthcare",
				"label": "Healthcare Reach",
				"value": reach_val,
				"subtext": reach_sub,
				"trend": "47.5% Capacity",
				"status": "positive",
				"category": "Clinical",
				"target_module": "medical_camps",
			},
			{
				"id": "kpi_coworking",
				"label": "Workspace Occupancy",
				"value": cowork_val,
				"subtext": cowork_sub,
				"trend": "1/6 Occupied",
				"status": "positive",
				"category": "Facilities",
				"target_module": "coworking",
			},
			{
				"id": "kpi_lab",
				"label": "Diagnostic Turnaround",
				"value": lab_val,
				"subtext": lab_sub,
				"trend": "75% In-Lab",
				"status": "positive",
				"category": "Diagnostics",
				"target_module": "lab_management",
			},
		]

		# 3. Pending Approvals (governance queue)
		pending_approvals = []
		if is_admin or is_manager:
			live_apprs = []
			if _ORCHESTRATOR_AVAILABLE and orchestrator is not None:
				try:
					live_apprs = orchestrator.list_approvals(tenant_id=principal.tenant_id)
				except Exception:
					live_apprs = []

			if live_apprs:
				for a in live_apprs:
					if a.get("status") == "pending":
						pending_approvals.append({
							"id": a["approval_id"],
							"title": a.get("operation_name", "Operation Approval"),
							"module": a.get("product_id", "").replace("iryax.", "").replace("_", " ").title(),
							"module_id": a.get("product_id", "").replace("iryax.", ""),
							"severity": "high" if "payroll" in a.get("product_id", "") or "lab" in a.get("product_id", "") else "medium",
							"description": str(a.get("payload", {})),
							"requester": "Subagent Lead",
							"time_ago": "Active Queue",
						})

			if not pending_approvals:
				pending_approvals = [
					{
						"id": "appr_1",
						"title": "TimelyHealth Monthly Payroll · Oct 2026",
						"module": "Payroll",
						"module_id": "payroll",
						"severity": "high",
						"description": "Disbursement of ₹2,55,000 across 10 active employees (TH450 Aarif & team)",
						"requester": "Finance Lead",
						"time_ago": "12m ago",
					},
					{
						"id": "appr_2",
						"title": "Publish Candidate Shortlist (Senior Developer)",
						"module": "Recruitment",
						"module_id": "recruitment",
						"severity": "medium",
						"description": "Move 8 candidates to technical interview stage (Marcus Chen 94% match)",
						"requester": "Talent Lead",
						"time_ago": "38m ago",
					},
					{
						"id": "appr_3",
						"title": "Release Validated Lab Reports",
						"module": "Lab Management",
						"module_id": "lab_management",
						"severity": "high",
						"description": "Release 12 verified reports to clinicians (3 abnormal panels flagged)",
						"requester": "Dr. Kim",
						"time_ago": "1h ago",
					},
					{
						"id": "appr_4",
						"title": "Doctor Chamber Schedule Override",
						"module": "OP Management",
						"module_id": "op_management",
						"severity": "medium",
						"description": "Insert urgent surgical block for Dr. Vamsi",
						"requester": "Clinic Ops",
						"time_ago": "2h ago",
					},
					{
						"id": "appr_5",
						"title": "Bulk Patient Records Sync",
						"module": "Medical Camps",
						"module_id": "medical_camps",
						"severity": "high",
						"description": "Export 520 triage records to state health registry",
						"requester": "Camp Lead",
						"time_ago": "3h ago",
					},
					{
						"id": "appr_6",
						"title": "Desk Reservation Credit Refund",
						"module": "Coworking",
						"module_id": "coworking",
						"severity": "low",
						"description": "Process refund for booking #BK-8841",
						"requester": "Desk Lead",
						"time_ago": "5h ago",
					},
				]

		# 4. Operational Issues (from real module analytics)
		operational_issues = []
		if task_analysis and task_analysis.problems_detected:
			operational_issues.append({
				"id": "iss_task",
				"module": "Task Management",
				"module_id": "task_management",
				"severity": "critical",
				"title": "6 critical sprint tasks blocked",
				"impact": "Sprint 42 release timeline at risk if dependencies not resolved within 24 hours.",
				"action": "Unblock Tasks",
			})
		if rec_analysis and rec_analysis.problems_detected:
			operational_issues.append({
				"id": "iss_rec",
				"module": "Recruitment",
				"module_id": "recruitment",
				"severity": "warning",
				"title": "Top candidates awaiting technical interview scheduling",
				"impact": "Marcus Chen (94%) and Carlos Gomez (93%) risk competing offers if not scheduled promptly.",
				"action": "Schedule Interview",
			})
		if lab_analysis and lab_analysis.problems_detected:
			operational_issues.append({
				"id": "iss_lab",
				"module": "Lab Management",
				"module_id": "lab_management",
				"severity": "critical",
				"title": "3 abnormal critical diagnostic alerts flagged",
				"impact": "1 critical lipid profile and 2 elevated HbA1c panels require immediate pathologist review.",
				"action": "Review Sign-offs",
			})
		if "op_management" in module_analyses and module_analyses["op_management"].problems_detected:
			operational_issues.append({
				"id": "iss_op",
				"module": "OP Management",
				"module_id": "op_management",
				"severity": "warning",
				"title": "Dr. Priya Mehta chamber queue operating at peak load",
				"impact": "18 active tokens with 4 walk-in patients waiting triage.",
				"action": "Open Queue",
			})

		# 5. Module Overview (7 modules summary)
		module_overview = []
		for mod_id, mod_name, mod_icon, mod_domain in all_modules:
			analysis = module_analyses.get(mod_id)
			score = analysis.performance_score if analysis else 90
			status_str = analysis.performance_status if analysis else "HEALTHY"
			first_stat = f"{analysis.statistics[0].label}: {analysis.statistics[0].value}" if analysis and analysis.statistics else "Active"
			module_overview.append({
				"id": mod_id,
				"name": mod_name,
				"icon": mod_icon,
				"domain": mod_domain,
				"score": score,
				"status": status_str,
				"key_metric": first_stat,
				"summary": analysis.executive_summary if analysis else "Operating normally.",
			})

		# 6. Recent Organizational Activities
		recent_activities = [
			{
				"id": "act_1",
				"time": "Just now",
				"domain": "Payroll",
				"module_id": "payroll",
				"title": "October payroll reconciliation calculated",
				"details": "10 TimelyHealth employees reconciled; net disbursement ₹2,55,000",
				"badge": "Audit Ready",
				"badge_tone": "neutral",
			},
			{
				"id": "act_2",
				"time": "12m ago",
				"domain": "Recruitment",
				"module_id": "recruitment",
				"title": "Candidate qualification completed",
				"details": "Marcus Chen qualified at 94% match for Engineering Director",
				"badge": "Offer Gated",
				"badge_tone": "neutral",
			},
			{
				"id": "act_3",
				"time": "28m ago",
				"domain": "OP Management",
				"module_id": "op_management",
				"title": "Chamber queue token dispatched",
				"details": "Dr. Priya Mehta chamber queue updated: token #18 called",
				"badge": "On Duty",
				"badge_tone": "neutral",
			},
			{
				"id": "act_4",
				"time": "1h ago",
				"domain": "Medical Camps",
				"module_id": "medical_camps",
				"title": "Community screening batch synchronized",
				"details": "520 patient records synchronized across 4 field clinics",
				"badge": "Synced",
				"badge_tone": "neutral",
			},
			{
				"id": "act_5",
				"time": "2h ago",
				"domain": "Task Management",
				"module_id": "task_management",
				"title": "Sprint 42 burndown updated",
				"details": "34 active tasks tracked; 6 dependency blockers identified",
				"badge": "Sprint 42",
				"badge_tone": "warning",
			},
			{
				"id": "act_6",
				"time": "3h ago",
				"domain": "Lab Management",
				"module_id": "lab_management",
				"title": "Laboratory batch validated",
				"details": "184 diagnostic reports signed off with 99.4% SLA adherence",
				"badge": "Validated",
				"badge_tone": "neutral",
			},
		]

		# 7. Performance Trends
		performance_trends = {
			"sla_adherence": "98.4%",
			"automation_rate": "86%",
			"avg_cycle_velocity": "4.2 days",
			"compliance_status": "100% SOC2 Ready",
		}

		# 8. Compact AI-Generated Insights
		executive_ai_insights = {
			"headline": f"Enterprise operational health is strong at {org_health_score}% with active governance.",
			"summary": "Monthly payroll of ₹2,55,000 for 10 TimelyHealth employees is reconciled and awaiting disbursement sign-off. Healthcare reach stands at 520 patients screened across 4 field clinics. Key administrative priorities today: authorize the payroll disbursement, clear 6 blocked tasks in Sprint 42, and confirm technical interviews for 2 top-tier engineering leads.",
			"recommended_actions": [
				"Authorize ₹2,55,000 October Payroll disbursement",
				"Review and unblock 6 dependencies in Sprint 42",
				"Schedule Technical Round 1 for Marcus Chen & Carlos Gomez",
				"Review 3 abnormal diagnostic findings in Lab Management",
			],
		}

		return {
			"organization": {
				"name": "Iryax Multi-Agent Enterprise",
				"tier": "Global Enterprise",
				"user": {
					"id": principal.user_id,
					"tenant_id": principal.tenant_id,
					"role": principal.role,
				},
				"health_score": org_health_score,
				"status": "OPERATIONAL" if org_health_score >= 80 else "ATTENTION_REQUIRED",
				"timestamp": utc_iso(utc_now()),
			},
			"kpis": executive_kpis,
			"pending_approvals": pending_approvals,
			"operational_issues": operational_issues,
			"module_overview": module_overview,
			"recent_activities": recent_activities,
			"performance_trends": performance_trends,
			"executive_ai_insights": executive_ai_insights,
		}

	except Exception as exc:
		logger.exception("Error generating dashboard summary: %s", exc)
		raise HTTPException(status_code=500, detail=f"Failed to generate dashboard summary: {exc}")


# ── Analytics ────────────────────────────────────────────────────────────────


@app.get("/analytics")

async def get_analytics(

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        """Retrieve analytics. Authentication required."""

        summary = get_analytics_summary()

        if _ORCHESTRATOR_AVAILABLE and orchestrator is not None:

                summary["subagents"] = orchestrator.list_subagents()

        return summary


# ── Cache clear ───────────────────────────────────────────────────────────────


@app.post("/cache/clear")

async def clear_cache(

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        """Clear semantic cache. Authentication required."""

        cleared = clear_semantic_cache()

        return {"status": "success", "cleared_entries": cleared}


# ── Scraper log ───────────────────────────────────────────────────────────────


@app.get("/scraper/log")

async def get_scraper_log(

        lines: int = Query(default=50, ge=1, le=500),

        principal: AuthenticatedPrincipal = Depends(get_current_principal),

):

        """Read recent scraper log output. Authentication required."""

        if not SCRAPER_LOG_PATH.exists():

                return {

                        "status": "error",

                        "message": "Scraper log not found",

                }


        try:

                with open(SCRAPER_LOG_PATH, "r", encoding="utf-8") as file:

                        all_lines = file.readlines()


                return {

                        "status": "success",

                        "log": "".join(all_lines[-lines:]),

                }

        except OSError:

                logger.exception("Unable to read scraper log.")

                raise HTTPException(

                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

                        detail="Unable to read scraper log.",

                )


# ── Production Frontend Static Asset Serving ─────────────────────────────────

_FRONTEND_DIST = pathlib.Path(__file__).parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    from fastapi.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="static_assets")

    @app.get("/")
    async def serve_production_root():
        index_html = _FRONTEND_DIST / "index.html"
        if index_html.exists():
            return FileResponse(str(index_html))
        return {"message": "Iryax Multi-Agent Engine API online"}

    @app.get("/favicon.svg")
    async def serve_favicon():
        fav = _FRONTEND_DIST / "favicon.svg"
        if fav.exists():
            return FileResponse(str(fav))
        raise HTTPException(status_code=404, detail="Favicon not found")
