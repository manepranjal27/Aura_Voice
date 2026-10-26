# Aura Skincare — Aria Customer Experience Demo

A responsive skincare landing page and customer-support demo built on the existing Aura Voice AI project. It preserves the FastAPI backend and `data/orders.json` order source while adding product interactions, a floating animated Aria robot, browser speech controls, policy-aware support responses, and a post-call transcript/JSON summary.

## Features

- Premium green-and-cream skincare homepage with responsive navigation and product photography.
- Product category filters, general preference filter, quick-view modals, FAQ accordion, smooth anchors and reduced-motion support.
- Floating CSS robot character named Aria and expandable assistant panel.
- Browser speech recognition and speech synthesis where supported; text chat remains available.
- FastAPI-backed order lookup and support endpoint.
- Policy responses for shipping, returns, cancellations, COD and out-of-scope questions.
- Evaluator helper for ORD-101, ORD-102 and ORD-103.
- Chronological transcript, structured summary and Copy JSON control.

## Architecture

```text
Browser (HTML/CSS/JavaScript)
  ├─ Browser Speech Recognition (when supported)
  ├─ Browser Speech Synthesis (when supported)
  └─ HTTP requests
       ↓
FastAPI (`main.py`)
  ├─ GET /api/health
  ├─ GET /api/orders/{order_id}
  ├─ GET /api/orders
  └─ POST /api/chat (policy-based response engine)
       ↓
`data/orders.json` (demo order records)
```

**Important limitation:** this version is a functional, policy-based voice support starter, not an LLM-connected AI agent. `/api/chat` uses deterministic rules, and the browser supplies speech recognition/synthesis. It does not perform actual cancellation, refunds, or other order changes. A real LLM and provider tool/function calling can be added using a server-side API key; no API key is required for the current demo. Do not describe the current implementation as a connected LLM voice agent.

## Technology stack

- Frontend: semantic HTML, CSS, vanilla JavaScript.
- Backend: Python, FastAPI, Pydantic.
- Order source: JSON file for assessment demonstration.
- Voice: browser Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition` and `speechSynthesis`).

## Project structure

```text
aura-voice-ai/
├── main.py
├── requirements.txt
├── .env.example
├── README.md
├── data/orders.json
├── static/index.html
├── static/style.css
└── static/script.js
```

The bundled virtual environment from the original ZIP is intentionally excluded. Create a fresh environment on your own machine.

## Run locally (Windows PowerShell)

1. Extract the ZIP and open a terminal in the `aura-voice-ai` folder.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` if you need to change CORS settings. The app currently reads `CORS_ORIGINS` from the process environment; it does not automatically parse `.env`. For local use, defaults are already suitable.
4. Start the server:

   ```powershell
   uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```
5. Open `http://127.0.0.1:8000`.

## API quick checks

- Health: `GET http://127.0.0.1:8000/api/health`
- One order: `GET http://127.0.0.1:8000/api/orders/ORD-101`
- All demo orders: `GET http://127.0.0.1:8000/api/orders`
- Support response: `POST http://127.0.0.1:8000/api/chat` with JSON body `{"message":"Where is my order ORD-101?"}`

The browser UI and API are served from the same origin, so the default frontend does not hardcode localhost. For a separately hosted frontend, define `window.AURA_API_BASE` before `script.js` and set `CORS_ORIGINS` to the frontend's exact origin on the backend.

## Voice setup and limitations

- Use a modern browser such as Chrome or Edge. Speech recognition support differs by browser and OS.
- Microphone permission is required. Browsers generally require HTTPS or a secure localhost context.
- If recognition is unavailable, the text chat and sample order helper still work.
- Voice language is set to Indian English (`en-IN`); Aria's spoken response switches to Hindi when the response contains Devanagari text. Hindi/Hinglish recognition can be expanded by changing `instance.lang` in `static/script.js`.
- Browser speech services may process audio according to browser/provider terms; do not enter sensitive personal or payment data.

## Policy rules included

- Shipping: free above ₹499; below ₹499, ₹50 shipping; standard delivery 3–5 business days.
- Returns: within 7 days of delivery for unopened, unused products in original packaging.
- Damaged/defective items: report within 48 hours with photos for replacement.
- Cancellation: only while Processing; shipped and Out for Delivery orders cannot be cancelled; customer may refuse delivery.
- COD: up to ₹2,500, cash or UPI at the doorstep.

Cancellation is eligibility information only. The demo intentionally does not claim an order was cancelled because no cancellation mutation endpoint exists.

## Test checklist

1. Open the site and verify product navigation and section links.
2. Filter products by Serums, Cleansers and Hydration & sun care.
3. Change the preference selector and open/close each product quick-view.
4. Expand FAQ rows.
5. Open Aria, minimize and reopen the panel.
6. Use evaluator buttons for ORD-101, ORD-102 and ORD-103; details should load from FastAPI.
7. Type `Where is my order ORD-101?` and verify the answer uses backend order details.
8. Type `When will ORD-101 arrive?` and verify the expected-delivery details are returned.
9. Type `Can I cancel ORD-103?`; Aria should explain eligibility but not claim cancellation occurred.
10. Type `Can I cancel ORD-101?`; Aria should explain cancellation is not permitted for Out for Delivery.
11. Type `Can I return ORD-102?`; Aria should explain the 7-day window and that this order is 14 days old.
12. Ask `What are your shipping charges?`, `Where is ORD-999?`, and `Can you book a flight?`.
13. Stop the server and try an order lookup; the UI should show a friendly connection error.
14. Start a call in a supported browser, grant microphone access, speak, then end the call and copy the summary JSON.
15. Check layout on a narrow mobile viewport and desktop.

Voice checks depend on browser speech API support and microphone permission. The code has not been deployed publicly by this repository package.

## Assessment answers

### 1. Why this architecture and technology stack?

The existing project uses a small HTML/CSS/JavaScript frontend and FastAPI backend, so retaining them avoids a needless rewrite and keeps the demo straightforward to run. FastAPI exposes typed HTTP endpoints and validates input. The order lookup tool reads the order source instead of asking a language model to guess order facts. Browser speech APIs provide a low-dependency voice prototype, while the frontend keeps transcript and UI state. A production version should connect a server-side LLM with tool/function calling and keep all credentials on the backend.

### 2. Most difficult part and how it was solved

The original JavaScript referenced an `orders` object that was not defined in that file, which could break order questions. The updated frontend requests order information from FastAPI instead. Business-policy responses are handled in a backend policy function, and order status/details are retrieved from the existing JSON source. The current build is a rule-based starter, so it does not claim that an LLM integration or order mutation was completed.

### 3. What would be improved with one more week?

First, connect a hosted LLM with server-side tool/function calling and tests that verify tool results are used. Then replace JSON with a persistent database, add authenticated customer access and real cancellation workflow with explicit confirmation, improve voice interruption and multilingual support, and add automated browser/API tests plus accessibility checks.

### 4. How to scale to 1,000 conversations per day?

Use an async FastAPI deployment behind a managed load balancer, store orders in a reliable database with indexed order IDs, and keep conversation/session state in a suitable shared store rather than process memory. Queue slow tasks, apply timeouts and retries to external AI/voice providers, rate-limit by session/IP, cap tokens and audio duration, cache stable policy answers, and use concurrency limits to control provider spend. Add structured logs without sensitive data, metrics for latency/error rate/tool-call success, tracing, alerts, health checks, secrets management, and load tests. One thousand conversations per day averages only about 0.012 conversations/second over a full day, but peaks and simultaneous live calls drive capacity planning more than the daily average.

## Deployment

Deploy the FastAPI app to a Python-capable service (for example, Render or Railway) using the start command `uvicorn main:app --host 0.0.0.0 --port $PORT`. Set `CORS_ORIGINS` to the exact public frontend origin if the frontend is hosted separately. This repository currently serves the frontend from FastAPI, so a single-service deployment is simplest. Configure HTTPS for microphone access. Add an LLM provider key only after implementing a provider integration, storing the key as a server-side environment variable. No public deployment is included or claimed by this ZIP.
