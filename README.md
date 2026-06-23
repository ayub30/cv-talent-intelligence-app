# CV Talent Intelligence App

Standalone React + FastAPI prototype for the CV management and talent intelligence system.

## Structure

- `frontend/` - Vite React app
- `backend/` - FastAPI app with `/ask`

## Run Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Set your LLM endpoint later:

```bash
export LLM_URL="https://your-llm-endpoint.example/ask"
```

If `LLM_URL` is empty, `/ask` returns a local mock response so the frontend remains usable.

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.
