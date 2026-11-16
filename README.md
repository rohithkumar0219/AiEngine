# Iryax AI-Engine Platform

The **Iryax AI-Engine** is a unified, enterprise AI platform combining high-speed cloud inference via the **Groq API**, semantic knowledge retrieval via **ChromaDB RAG**, and a multi-agent orchestration architecture supporting **Iryax's 7 vertical products**.

---

## 🏛️ System Architecture

```text
                        ┌────────────────────────────────────────┐
                        │      Frontend Clients & Portals        │
                        │  (Chat Widget, Admin, Agent Workspaces)│
                        └──────────────────┬─────────────────────┘
                                           │ HTTP / NDJSON Streaming
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        MAIN AI ENGINE: `chatbotbackend/`                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  • FastAPI Server (`api.py`)                                                          │
│    ├── POST /chat (Streaming NDJSON with token buffering & citation links)           │
│    ├── GET  /analytics (Query volume, latency distribution, cache hit rates)         │
│    ├── POST /feedback (User thumbs up/down feedback logging)                         │
│    └── POST /cache/clear (Semantic cache invalidation)                                │
│                                                                                        │
│  • RAG & LLM Engine (`rag_pipeline.py`, `groq_adapter.py`)                            │
│    ├── Groq Cloud Client (ultra-fast inference using `openai/gpt-oss-120b`)           │
│    ├── ChromaDB Vector Store (`iryax_context_v2` collection)                          │
│    ├── Semantic Response Cache (Cosine similarity matching)                           │
│    └── Automated Content Decoupling & Scraper (`scraper.py`)                          │
│                                                                                        │
│  • Platform Base Layer (`iryax_platform/`)                                             │
│    ├── RBAC Authorization & Tenant Context                                            │
│    ├── Human-in-the-Loop (HITL) Approval Gating                                       │
│    └── Immutable Audit Trail Logging                                                  │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     VERTICAL AGENT MODULES: `subagents/`                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  1. Recruitment Agent         — Resume parsing, candidate scoring, offer gating       │
│  2. Attendance & Payroll      — Shift reconciliation, draft payroll, payout approvals │
│  3. Task Management           — Task decomposition, blocker alert, deletion gating    │
│  4. Medical Camps             — Patient intake, vitals triage, export approvals       │
│  5. OP Management             — Queue token issuance, slot booking, override gating   │
│  6. Coworking Space           — Desk/cabin booking, billing, refund approvals         │
│  7. Lab Management            — Test ordering, abnormal result flags, release gating  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Repository Structure

```text
AI-Engine/
├── frontend/                       # React 19 + Vite 8 + Tailwind CSS v4 Frontend App
│   ├── src/                        # UI Components (Assistant, Agents, Approvals, Analytics)
│   │   ├── App.tsx                 # Main application shell with live backend integration
│   │   ├── index.css               # Global styling, tokens, and dark/light themes
│   │   └── main.tsx                # Entrypoint
│   ├── public/                     # Static assets & icons
│   ├── index.html                  # Vite HTML root shell
│   ├── vite.config.ts              # Vite configuration with proxy to http://127.0.0.1:8000
│   ├── package.json                # Frontend dependencies & build scripts
│   └── tsconfig.json               # TypeScript configuration
│
├── backend/                        # Complete FastAPI AI Engine & Multi-Agent Backend
│   ├── api.py                      # FastAPI routes & streaming NDJSON endpoint (/chat)
│   ├── rag_pipeline.py             # Groq RAG pipeline, semantic cache, ChromaDB search
│   ├── groq_adapter.py             # Official Groq SDK adapter with credential redaction
│   ├── agent_bridge.py             # Multi-agent streaming bridge with context injection
│   ├── scraper.py                  # Standalone Playwright web scraper & indexer
│   ├── generate_intents.py         # Structured intent generator powered by Groq
│   ├── iryax_platform/             # Enterprise platform protocols (core + product agents)
│   ├── subagents/                  # 7 Modular Multi-Product AI Agent Packages
│   │   └── src/anycode/agents/products/ (Recruitment, Payroll, Tasks, Camps, OP, Coworking, Lab)
│   ├── data/                       # Vector store persistence & raw/processed scraped chunks
│   ├── tests/                      # Comprehensive test suite (22 unit & integration tests)
│   ├── requirements.txt            # Python dependencies (fastapi, groq, chromadb, etc.)
│   └── .env                        # Local environment configuration
│
└── README.md                       # Master Architecture & Technical Specifications
```

---

## 🔌 Backend API Specification

### 1. Streaming Chat (`POST /chat`)
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "question": "What plans and pricing does Iryax offer?",
    "history": [
      {"role": "user", "content": "Hi"},
      {"role": "assistant", "content": "Hello! How can I assist you today?"}
    ],
    "session_id": "sess_user_9921",
    "website_id": "https://iryax.com"
  }
  ```
- **Response Format**: `application/x-ndjson` (Newline-Delimited JSON)
  - **Streaming Tokens**:
    ```json
    {"token": "Iryax ", "sources": ["https://iryax.com/pricing"]}
    {"token": "offers ", "sources": ["https://iryax.com/pricing"]}
    {"token": "four flexible tiers...", "sources": ["https://iryax.com/pricing"]}
    ```
  - **Final Completion Line** (token is empty to prevent duplication):
    ```json
    {
      "token": "",
      "sources": ["https://iryax.com/pricing"],
      "answer": "Iryax offers four flexible tiers: Starter, Growth, Pro, and Enterprise...",
      "session_id": "sess_user_9921"
    }
    ```

### 2. Feedback (`POST /feedback`)
- **Request Body**:
  ```json
  {
    "query": "What plans does Iryax offer?",
    "rating": "thumbs_up",
    "comment": "Accurate pricing details!"
  }
  ```

### 3. Analytics (`GET /analytics`)
- **Response**:
  ```json
  {
    "total_queries": 420,
    "cache_hit_rate_pct": 34.5,
    "avg_latency_ms": 312.4,
    "route_distribution": {
      "semantic_cache": 145,
      "rag_llm": 275
    }
  }
  ```

---

## 🖥️ Frontend Specification & Page Requirements

To turn the AI Engine into a complete web platform, the frontend must implement the following **5 core pages/views**:

---

### Page 1: AI Assistant Chat Interface (Widget & Full-Page View)
> **Purpose**: Public-facing customer support, visitor navigation, and product inquiry assistant.

#### UI Components & Elements:
1. **Header Bar**:
   - Iryax AI logo, live connectivity indicator (Online/Connecting/Offline via `GET /health`).
   - "Clear Conversation" button (resets local history and session ID).
   - Theme toggle (Dark / Light mode).
2. **Message Scroll Area**:
   - Distinct speech bubbles for `user` and `assistant`.
   - **Real-Time Streaming Render**: Parses `application/x-ndjson` stream line-by-line without screen flickering.
   - **Rich Markdown Support**: Full GitHub Flavored Markdown renderer supporting lists, bold text, tables, and formatted links.
   - **Citation Pills**: Clickable source tags beneath assistant answers (e.g., `[Source: Pricing Page ↗]` or `[About Us ↗]`).
   - **Clickable Contact Action Buttons**: Auto-formatted `tel:` and `mailto:` links for one-tap calling or emailing.
3. **Feedback Widget**:
   - Thumbs-up (`👍`) and Thumbs-down (`👎`) buttons attached to completed assistant responses.
   - Popover for optional feedback comments, submitting to `POST /feedback`.
4. **Input Area**:
   - Expanding multi-line text input with Enter-to-send (Shift+Enter for new line).
   - Quick Suggestion Prompts / Chips (e.g. *"What is Iryax?"*, *"Pricing Tiers"*, *"Book a Coworking Desk"*, *"Schedule Camp"*).
   - Disabled state with subtle pulse animation during generation.

---

### Page 2: Iryax 7-Product Agent Workspaces
> **Purpose**: Internal domain portals where authorized staff interact with specialized vertical agents to run business workflows.

#### Common Workspace Architecture:
- **Product Switcher**: Navigation sidebar or tabs switching between the 7 products:
  1. Recruitment
  2. Attendance & Payroll
  3. Task Management
  4. Medical Camps
  5. OP Clinic Management
  6. Coworking Space
  7. Lab Management
- **Role Badge**: Displays current actor's authenticated role (e.g., `admin`, `doctor`, `hr_manager`, `cashier`).
- **Workflow Action Bar**: Quick action buttons executing high-level workflows.

#### Specific Requirements by Product:

| Product Workspace | Dedicated UI Panels & Input Forms | Live Visualizations & Outputs |
| :--- | :--- | :--- |
| **1. Recruitment** | • Job Description Creator<br>• Resume File Dropzone (.pdf, .docx, raw text)<br>• Role Criteria Sliders (Experience, Tech Stack) | • Candidate Match Score Meter (0–100%)<br>• Parsed Skills & Experience Pills<br>• Interview Scheduling Calendar preview |
| **2. Payroll & Attendance** | • Shift Attendance CSV Uploader<br>• Pay Period Selector<br>• Overtime Multiplier Form | • Reconciliation Anomaly Table (Flags missed punches)<br>• Draft Payroll Ledger Summary<br>• Gross vs. Net payout breakdown charts |
| **3. Task Management** | • Project Goal & Epic Input Box<br>• Assignee & Sprint Target Picker<br>• Dependency Selector | • Automated Task Decomposition DAG View<br>• Blocker & Bottleneck Alert Cards (Red/Yellow badge)<br>• Critical Path timeline |
| **4. Medical Camps** | • Rapid Patient Intake Form (Name, Age, BP, Sugar, Pulse)<br>• Camp Location & Station Selector | • Clinical Urgency Triage Badge (`Normal`, `Urgent`, `Critical`)<br>• Doctor referral routing table<br>• Camp attendance counter |
| **5. OP Management** | • Doctor Schedule & Specialty Dropdown<br>• Patient Appointment Booking Form | • Live Virtual Queue Token Display (`Token #A-14 Now Serving`)<br>• Doctor Availability Heatmap<br>• Slot calendar |
| **6. Coworking Space** | • Floor Plan / Zone Selector (Flexi-desk, Dedicated, Cabin)<br>• Date Range & Time Slot Picker | • Interactive Desk Map (Green = Available, Red = Booked)<br>• Invoice & Booking Summary Modal<br>• Cancellation & Refund eligibility badge |
| **7. Lab Management** | • Diagnostic Order Form (Test Code, Specimen ID, Patient ID)<br>• Specimen Intake Barcode Scanner input | • Lab Order Status Pipeline (Collected ➔ Processing ➔ Reviewed)<br>• Abnormal Reference Range Highlight (Out-of-bound values in red) |

---

### Page 3: Human-in-the-Loop (HITL) & Compliance Approval Hub
> **Purpose**: Governance dashboard for operations managers and compliance officers to review and approve sensitive agent actions before execution.

#### UI Components & Elements:
1. **Pending Approvals Queue**:
   - Filter by product type, risk severity (High / Medium), and submission timestamp.
   - Cards displaying:
     - **Action Type**: (e.g., `payroll:disburse_funds`, `recruitment:send_offer`, `coworking:process_refund`, `medical_camps:bulk_export`).
     - **Requesting Agent & User**: Context actor ID and product tenant.
     - **Payload Diff / Summary**: Clean table displaying proposed amounts, candidate salary, or exported record count.
2. **Approval Action Controls**:
   - **Approve Button** (Green, triggers execution with user digital signature/audit note).
   - **Reject Button** (Red, requires mandatory rejection reason modal).
   - **Request Changes / Edit** (Allows modifying parameters before approving).
3. **Audit Trail Log Table**:
   - Real-time immutable record of past approvals and rejections (`timestamp`, `reviewer_id`, `action`, `status`, `duration_ms`).
   - Export audit log to CSV/JSON.

---

### Page 4: Analytics, Telemetry & Semantic Cache Dashboard
> **Purpose**: DevOps, engineering, and product monitoring dashboard backed by `GET /analytics`.

#### UI Components & Elements:
1. **KPI Metric Cards**:
   - **Total Queries Served**: Aggregate counter.
   - **Average Response Latency**: Gauge in milliseconds (sub-500ms target).
   - **Cache Hit Rate**: Percentage of requests served directly from the semantic cache.
   - **Error Rate**: Ratio of failed inferences or rate limits.
2. **Interactive Visualizations**:
   - **Routing Distribution Donut Chart**: `Semantic Cache` vs `Groq RAG LLM`.
   - **Latency Time-Series**: Line chart showing latency fluctuations over the last 24h.
   - **Top Inquired Topics / Intents**: Bar chart ranking popular categories (Pricing, Features, Support, Coworking).
3. **Cache Management Panel**:
   - In-memory cache status (Number of active cached query-response pairs).
   - **"Clear Semantic Cache" Button**: Triggers `POST /cache/clear` with confirmation dialog and toast notification.

---

### Page 5: Knowledge Base & Scraper Control Center
> **Purpose**: Manage the data ingested into ChromaDB and monitor automated Playwright scraping.

#### UI Components & Elements:
1. **Scraper Activity Feed & Controls**:
   - Status Indicator (Idle / Scraping / Locked).
   - Manual **"Trigger Scraper Run"** action button.
   - **Live Log Viewer**: Auto-refreshing terminal-like viewer pulling from `GET /scraper/log?lines=100`.
2. **Indexed Knowledge Explorer**:
   - Table of indexed URLs from `iryax.com` (About, Pricing, Career, Products).
   - Chunk count per URL and last indexed timestamp.
   - Inspect raw markdown extracted per page.

---

## 🛠️ Frontend Technical Stack & Implementation Guidelines

When building the frontend web application, adhere to the following standards:

1. **Recommended Framework**: React / Next.js (TypeScript) or Vite + Vanilla CSS.
2. **Design Language & Styling**:
   - Modern glassmorphism with curated deep dark mode (`#0B0F19`, `#111827`, `#1F2937`) and clean light mode.
   - Vibrant accent palette: Primary Purple (`#7C3AED`), Cyan (`#06B6D4`), and Emerald (`#10B981`).
   - Typography: Clean modern fonts (Inter or Outfit from Google Fonts).
3. **NDJSON Stream Processing**:
   - Use the native browser `fetch()` API with `ReadableStreamDefaultReader` and `TextDecoder`.
   - Split incoming stream chunks by newline (`\n`), parse valid JSON objects, and append `token` chunks to the active message state.
   - Example reader snippet:
     ```typescript
     const response = await fetch("http://localhost:8000/chat", {
       method: "POST",
       headers: { "Content-Type": "application/json" },
       body: JSON.stringify({ question: userQuery, history })
     });
     
     const reader = response.body?.getReader();
     const decoder = new TextDecoder("utf-8");
     let buffer = "";

     while (reader) {
       const { value, done } = await reader.read();
       if (done) break;
       buffer += decoder.decode(value, { stream: true });
       const lines = buffer.split("\n");
       buffer = lines.pop() || "";
       for (const line of lines) {
         if (line.trim()) {
           const payload = JSON.parse(line);
           if (payload.token) updateStreamingMessage(payload.token);
           if (payload.sources) setSources(payload.sources);
         }
       }
     }
     ```

---

## 🧪 Testing and Verification

Verify the entire engine locally:

```bash
# 1. Run Main Backend tests (22 tests covering GroqAdapter, AgentBridge, and Scraper)
cd backend
python -m unittest discover -s tests -v

# 2. Run Product Agent tests (40 tests covering all 7 products, RBAC, and HITL gates)
cd subagents
$env:PYTHONPATH="src"; python -m pytest -v
```

---

## 📜 License & Compliance

Confidential & Proprietary — **Iryax AI / Ingrain Brands**. All rights reserved.
