# Procure-IQ 🤖
### Intelligent Autonomous Procurement System

> An AI-powered backend that continuously monitors your Gmail inbox, detects invoices, manages inventory stock levels, and automates purchase approvals — end to end, with minimal human intervention.

---

## ✨ Features

### 🧠 AI-Powered Invoice Detection
- **LangChain + Gemini 1.5 Flash** classifies every email as invoice or not (temperature=0.0, max_tokens=512)
- Extracts: vendor name, amount, invoice number, dates, currency — structured JSON output
- **PDF attachment parsing** via `pdfplumber` (first 5 pages)
- Confidence score on every result

### 📬 Gmail Inbox Agent
- Background agent polls **Inbox + Spam** every 60 seconds (configurable via `GMAIL_POLL_INTERVAL`)
- **Auto OAuth token refresh** — no manual re-auth needed
- Smart deduplication: by Gmail message ID *and* by subject+sender (catches forwarded emails)
- All discovered invoices stored in `gmail_invoices` DB table with full audit trail

### 📦 Inventory Agent
- Monitors stock levels every 30 seconds against configurable thresholds
- Triggers low-stock alerts automatically
- Sends approval request to owner via **Email + SMS + WhatsApp** (Twilio)

### ✅ Approval Workflow
- Owner receives an email with a one-click Approve link
- On approval → purchase order email sent automatically to supplier
- Confirmation email sent back to owner
- Full audit trail logged per invoice

### 📊 Analytics Dashboard
- Spend by vendor with progress bars
- Approval rate, total approved spend, weekly invoice volume
- Real-time agent health status (Gmail agent + Inventory agent)
- 🧪 Test Invoice button to inject fake invoices for E2E testing

### 🛡️ Security
- Google OAuth2 login (session-based)
- API key authentication on all endpoints
- Rate limiting via `slowapi` (5 req/min on sensitive endpoints)
- Configurable allowed users list

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Gmail Agent  │  │  Inventory   │  │  Procurement     │  │
│  │ (60s poll)   │  │  Agent       │  │  Agent (Matcher) │  │
│  │              │  │  (30s poll)  │  │                  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────┘  │
│         │                 │                                  │
│  ┌──────▼─────────────────▼──────────────────────────────┐  │
│  │              SQLite Database                           │  │
│  │  gmail_invoices │ inventory │ alerts │ vendors │ users │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LangChain + Gemini 1.5 Flash (AI Brain)            │    │
│  │  temp=0.0  max_tokens=512  structured_output=True   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/your-repo/procure-iq.git
cd procure_iq_backend
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

### 3. Set Up Gmail OAuth
Run the one-time auth setup to get your refresh token:
```bash
python gmail_auth_setup.py
```
Copy the `GMAIL_REFRESH_TOKEN` printed to your `.env`.

### 4. Run the Server
```bash
python run.py
```
Open **http://localhost:8888** — agents start automatically.

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `GMAIL_CLIENT_ID` | ✅ | Gmail OAuth client ID |
| `GMAIL_CLIENT_SECRET` | ✅ | Gmail OAuth client secret |
| `GMAIL_REFRESH_TOKEN` | ✅ | Gmail OAuth refresh token |
| `GOOGLE_CLIENT_ID` | ✅ | Google Sign-In client ID |
| `GOOGLE_CLIENT_SECRET` | ✅ | Google Sign-In client secret |
| `SECRET_KEY` | ✅ | Session encryption key |
| `API_KEY` | ✅ | API authentication key |
| `OWNER_EMAIL` | ✅ | Owner email for alerts |
| `OWNER_PHONE` | ⭐ | Owner phone for SMS/WhatsApp (E.164 format, e.g. `+919894488506`) |
| `SUPPLIER_EMAIL` | ⭐ | Default supplier email |
| `TWILIO_ACCOUNT_SID` | ⭐ | Twilio account SID (for SMS/WhatsApp) |
| `TWILIO_AUTH_TOKEN` | ⭐ | Twilio auth token |
| `TWILIO_FROM_NUMBER` | ⭐ | Twilio phone number |
| `GMAIL_POLL_INTERVAL` | — | Seconds between inbox scans (default: `60`) |
| `INVOICE_APPROVAL_THRESHOLD` | — | Invoice amount requiring human approval (default: `1000`) |
| `DATABASE_URL` | — | Database URL (default: `sqlite:///./procure_iq.db`) |
| `PORT` | — | Server port (default: `8888`) |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Dashboard (protected) |
| `GET` | `/settings` | Settings page |
| `GET` | `/api/gmail-invoices` | List AI-detected Gmail invoices |
| `PATCH` | `/api/gmail-invoices/{id}/status` | Approve or reject an invoice |
| `GET` | `/api/analytics` | Spend analytics (vendor breakdown, rates) |
| `GET` | `/api/agent-status` | Live health of all background agents |
| `POST` | `/api/test/inject-invoice` | Inject a test invoice (rate limited: 5/min) |
| `GET` | `/api/inventory` | Current inventory levels |
| `GET` | `/api/alerts` | Active low-stock alerts |
| `POST` | `/api/owner/approve-refill/{id}` | Approve a restock order |
| `GET` | `/api/erp/current` | Current ERP connection status |
| `GET` | `/api/ai-status` | AI engine status |
| `GET` | `/auth/login` | Google OAuth login |
| `GET` | `/auth/callback` | OAuth callback |
| `GET` | `/metrics` | Prometheus metrics |

---

## 🗂️ Project Structure

```
procure_iq_backend/
├── app/
│   ├── agent/
│   │   ├── ai_client.py        # Gemini + GPT-4o AI brain
│   │   ├── matcher.py          # Vendor matching & invoice validation
│   │   ├── inventory_manager.py
│   │   └── worker.py           # Inventory agent loop
│   ├── api/
│   │   ├── approval_routes.py  # Owner approval endpoints
│   │   ├── invoices.py
│   │   └── ...
│   ├── services/
│   │   ├── ai_extractor.py     # LangChain + Gemini invoice extraction
│   │   ├── gmail_agent.py      # Background Gmail polling agent (v2)
│   │   ├── token_refresh.py    # Auto OAuth token refresh
│   │   ├── alert_service.py    # Email + SMS + WhatsApp alerts
│   │   └── email_service.py    # Gmail email ingestion
│   ├── templates/
│   │   ├── index.html          # Main dashboard
│   │   └── settings.html       # Settings page
│   ├── models.py               # SQLAlchemy models
│   ├── main.py                 # FastAPI app + all routes
│   ├── auth.py                 # Google OAuth login
│   └── database.py
├── gmail_auth_setup.py         # One-time Gmail OAuth setup
├── config.py                   # Centralized settings
├── requirements.txt
├── run.py                      # Server entrypoint
├── .env.example                # Environment variable template
├── docker-compose.yml
└── nixpacks.toml               # Railway deployment config
```

---

## 🐳 Docker

```bash
docker-compose up --build
```

---

## 🚢 Deploy to Railway

1. Push to GitHub
2. Connect repo in [Railway](https://railway.app)
3. Add all environment variables from the table above
4. Railway auto-detects `nixpacks.toml` — no additional config needed

---

## 🧪 Testing

Click the **🧪 Test Invoice** button on the dashboard to inject a fake invoice and verify the full pipeline without needing a real email.

Or via API:
```bash
curl -X POST http://localhost:8888/api/test/inject-invoice \
  -H "X-API-Key: your-api-key"
```

---

## 📄 License

MIT
