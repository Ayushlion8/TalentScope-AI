# TalentScope AI

FastAPI service for the SHL AI Intern take-home assignment. It provides a stateless conversational recommender for SHL Individual Test Solutions.

## What It Does

- `GET /health` returns `{"status":"ok"}`.
- `POST /chat` accepts a stateless message history and returns:

```json
{
  "reply": "string",
  "recommendations": [
    {
      "name": "string",
      "url": "string",
      "test_type": "K"
    }
  ],
  "end_of_conversation": false
}
```

The assistant can clarify vague requests, recommend 1-10 grounded SHL assessments, refine recommendations from conversation history, compare two assessments, and refuse off-topic, legal, non-SHL, general hiring advice, or prompt-injection requests.
`test_type` uses SHL short codes such as `K`, `P`, `A`, or comma-separated codes for multi-type products.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

By default the app reads `data/catalog.json`. To override it, set:

```bash
set CATALOG_PATH=data/catalog.json
set LOG_LEVEL=INFO
```

## Run Locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Chat example:

```bash
curl -X POST http://localhost:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"messages\":[{\"role\":\"user\",\"content\":\"I need a SQL skills assessment for a mid-level developer, remote testing preferred\"}]}"
```

Comparison example:

```bash
curl -X POST http://localhost:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Compare SQL (New) and SQL Server (New)\"}]}"
```

## Test

```bash
pytest -q
```

Current suite covers health, strict schema behavior, clarification, recommendations, refinement, comparison, refusal, catalog grounding, max recommendation count, and conversation cap handling.
It also checks evaluator-style SQL, Java, Python, and personality queries for Recall@10 quality.

## Catalog

The catalog lives in `data/catalog.json` and is loaded at startup on first use. The scraper in `scripts/scrape_catalog.py` targets SHL product catalog pages with `type=1`, which corresponds to Individual Test Solutions. Product URLs are preserved from the scraped catalog hrefs and must start with `https://www.shl.com/products/product-catalog/view/`.

To refresh the catalog:

```bash
python scripts/scrape_catalog.py
```

## Design Summary

- `app/main.py`: FastAPI entrypoint exposing only `/health` and `/chat`.
- `app/models.py`: Pydantic request and response contracts with extra fields forbidden.
- `app/catalog.py`: catalog loading, normalization, deterministic search, fuzzy name lookup, and comparison lookup.
- `app/policy.py`: stateless behavior routing for clarification, recommendation, comparison, refusal, and 8-turn cap.
- `tests/`: evaluator-facing behavior tests.

See `docs/approach.md` for retrieval and routing details.

## Deployment Notes

The service is deployment-ready for any Python web host that supports ASGI. Use:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Keep `data/catalog.json` deployed with the app, or set `CATALOG_PATH` to a mounted catalog file.

### Render Deployment

This repository includes `render.yaml`, `Procfile`, and `runtime.txt`.

1. Push the latest code to GitHub.
2. In Render, create a new Web Service from `https://github.com/Ayushlion8/TalentScope-AI`.
3. Use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Environment variables:
   - `CATALOG_PATH=data/catalog.json`
   - `LOG_LEVEL=INFO`
5. After deploy, verify:

```bash
curl https://YOUR-RENDER-APP.onrender.com/health
curl -X POST https://YOUR-RENDER-APP.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"I need a Java assessment for a mid-level developer"}]}'
```
