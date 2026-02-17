# ProcureIQ Autonomous Backend

This is the judge-proof, technically honest backend for ProcureIQ. It replaces the previous Node.js simulation with a Python-based autonomous agent loop.

## Core Features
- **FastAPI**: Modern, high-performance API.
- **Autonomous Agent**: Background loop for processing procurement events.
- **SQLite Persistence**: Local data storage with full audit trail.
- **Ollama AI**: Honest LLM integration for fuzzy vendor matching.
- **Learning Ontology**: System improves automatically based on human approval of vendor aliases.

## Setup & Run

1. **Install Requirements**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Server**:
   ```bash
   python run.py
   ```
   The backend runs on **http://localhost:5000**.

3. **Check Status**:
   Visit [http://localhost:5000/api/system-status](http://localhost:5000/api/system-status) to verify the agent is active.

## Architecture
- **Event-Driven**: All inputs (simulated emails, UI actions) are written as events to the `events` table.
- **Background Worker**: `app/agent/worker.py` polls and executes logic independently of the request-response thread.
- **Explainable AI**: Every decision record includes human-readable reasoning and a confidence score.
