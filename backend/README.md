# Iryax AI Assistant — Backend API & AI Engine

Production FastAPI RAG (Retrieval-Augmented Generation) & Multi-Product Agent backend service for the Iryax AI Assistant. Powered by the **Groq API** for high-speed inference, ChromaDB for semantic retrieval, and real-time streaming NDJSON responses.

---

## 🚀 Key Capabilities

- **Ultra-Fast Groq Inference**: Powered by official Groq cloud API models (`openai/gpt-oss-120b`, `llama-3.3-70b-versatile`, etc.) for sub-second responses.
- **RAG Retrieval Engine**: Persistent ChromaDB vector search (`iryax_context_v2`) over scraped site pages and verified knowledge chunks.
- **Streaming NDJSON Output**: Real-time token streaming over `POST /chat` with dynamic page citation and markdown link formatting.
- **Semantic Caching**: In-memory response caching with cosine-similarity matching to accelerate common inquiries.
- **Autonomous Multi-Product Agent Platform**: Integrated domain agents (`iryax_platform`) covering Recruitment, Payroll, Task Management, Medical Camps, OP Management, Coworking, and Lab Management.
- **Decoupled Web Scraper**: Standalone Playwright-based scraper and intent generator (`scraper.py`, `generate_intents.py`).

---

## 🛠️ Configuration (`.env`)

Create or update `.env` in the `chatbotbackend` root:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
CONTACT_EMAIL=info@ingrainsystem.com
CONTACT_PHONE=+91-9010481048
```

---

## 📦 Setup & Installation

```bash
cd chatbotbackend
python -m venv venv
.\venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

---

## 🚀 Running the API Server

```bash
# Run FastAPI server on port 8000
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Interactive Swagger documentation is available at:
- Local: [http://localhost:8000/docs](http://localhost:8000/docs)
- Production: [https://apichatbot.iryax.com/docs](https://apichatbot.iryax.com/docs)

---

## 📄 API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status |
| `POST` | `/chat` | Streamed AI response generation (NDJSON) |
| `GET` | `/chat` | Method guidance for client tools |
| `POST` | `/feedback` | User response ratings (`thumbs_up` / `thumbs_down`) |
| `GET` | `/analytics` | Query statistics, latency tracking, and cache hit rates |
| `POST` | `/cache/clear` | Invalidate in-memory response cache |
| `GET` | `/scraper/log` | Recent scraper activity log |

---

## 🧪 Running Tests

Run the test suite:

```bash
python -m unittest discover -s tests -v
```
