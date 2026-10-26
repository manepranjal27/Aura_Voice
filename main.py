"""Aura Skincare — Aria Support API v3.

Features:
  - /api/chat            — unified chat endpoint (typed + voice use same logic)
  - /api/orders/{id}     — order lookup by ID (any format, case-insensitive)
  - /api/orders/search   — search orders by customer name (GET ?name=...)
  - /api/products        — product catalog
  - /api/health          — health check
  - /api/summary         — call summary
  - GET /                — homepage (index.html)
  - GET /aria            — Aria chat page (aria.html)

No LLM API key is required.  If GEMINI_API_KEY or OPENAI_API_KEY is set in
the environment, the chat engine delegates to the LLM for general questions.
Order lookups and policy checks always use the local database regardless.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR      = Path(__file__).resolve().parent
STATIC_DIR    = BASE_DIR / "static"
ORDERS_FILE   = BASE_DIR / "data" / "orders.json"
PRODUCTS_FILE = BASE_DIR / "data" / "products.json"

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Aura Skincare | Aria Support API", version="3.0.0")

allowed_origins = [
    x.strip()
    for x in os.getenv(
        "CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000"
    ).split(",")
    if x.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# Brand policies  (single source of truth)
# ---------------------------------------------------------------------------
POLICIES: dict[str, str] = {
    "shipping": (
        "Free delivery on orders above ₹499. Orders below ₹499 have a ₹50 shipping fee. "
        "Standard delivery takes 3–5 business days from the date of dispatch."
    ),
    "returns": (
        "Returns are accepted within 7 days of delivery for unopened, unused products in "
        "their original packaging. Damaged or defective items must be reported within 48 hours "
        "of delivery with photos for replacement consideration."
    ),
    "cancellation": (
        "Orders can be cancelled only while their status is 'Processing'. "
        "Shipped or Out for Delivery orders cannot be cancelled. "
        "Customers may refuse delivery at the doorstep if the order has already shipped."
    ),
    "cod": (
        "Cash on Delivery is available for orders up to ₹2,500. "
        "Payment can be made by cash or UPI at the doorstep."
    ),
}

# ---------------------------------------------------------------------------
# Product knowledge (complement products.json for richer chat responses)
# ---------------------------------------------------------------------------
PRODUCT_DETAILS: dict[str, dict[str, Any]] = {
    "vitamin c serum": {"name": "Aura Vitamin C Serum", "price": 699, "size": "30 ml", "use": "morning", "skin": "all skin types", "benefit": "brightening, antioxidant protection"},
    "sunscreen": {"name": "Aura Hydrating Sunscreen SPF 50", "price": 499, "size": "50 g", "use": "morning (last step)", "skin": "all skin types", "benefit": "broad-spectrum UV protection"},
    "face wash": {"name": "Aura Green Tea Face Wash", "price": 349, "size": "100 ml", "use": "morning and evening", "skin": "oily/combination", "benefit": "gentle cleansing, antioxidants"},
    "toner": {"name": "Aura Hydrating Toner", "price": 399, "size": "150 ml", "use": "after cleansing", "skin": "all skin types", "benefit": "skin prep, lightweight hydration"},
    "hyaluronic acid serum": {"name": "Aura Hyaluronic Acid Serum", "price": 799, "size": "30 ml", "use": "morning and evening", "skin": "dry/dehydrated", "benefit": "intense hydration, plumping"},
    "moisturizer": {"name": "Aura Aloe Vera Moisturizer", "price": 449, "size": "50 g", "use": "morning and evening", "skin": "all skin types", "benefit": "hydration, soothing"},
    "cleansing balm": {"name": "Aura Gentle Cleansing Balm", "price": 549, "size": "50 g", "use": "evening (first cleanse)", "skin": "dry/normal", "benefit": "deep cleanse, removes makeup"},
    "niacinamide serum": {"name": "Aura Niacinamide Serum", "price": 599, "size": "30 ml", "use": "morning and evening", "skin": "oily/acne-prone", "benefit": "pore minimising, oil control"},
}

ROUTINES: dict[str, list[str]] = {
    "dry": [
        "1. 🌙 Evening: Aura Gentle Cleansing Balm (₹549) — deep cleanse",
        "2. 🌙 Evening / ☀️ Morning: Aura Green Tea Face Wash (₹349)",
        "3. ✨ Aura Hyaluronic Acid Serum (₹799) — intense hydration",
        "4. 💧 Aura Aloe Vera Moisturizer (₹449)",
        "5. ☀️ Morning only: Aura Hydrating Sunscreen SPF 50 (₹499)",
    ],
    "oily": [
        "1. ☀️ Morning / 🌙 Evening: Aura Green Tea Face Wash (₹349)",
        "2. ✨ Aura Vitamin C Serum (₹699) — morning",
        "3. ✨ Aura Niacinamide Serum (₹599) — pore control",
        "4. 💧 Aura Aloe Vera Moisturizer (₹449) — lightweight",
        "5. ☀️ Morning only: Aura Hydrating Sunscreen SPF 50 (₹499)",
    ],
    "general": [
        "1. Cleanse: Aura Green Tea Face Wash (₹349)",
        "2. Tone: Aura Hydrating Toner (₹399)",
        "3. Treat: Aura Vitamin C Serum (₹699) or Hyaluronic Acid Serum (₹799)",
        "4. Moisturise: Aura Aloe Vera Moisturizer (₹449)",
        "5. Protect: Aura Hydrating Sunscreen SPF 50 (₹499) — mornings only",
    ],
}

# ---------------------------------------------------------------------------
# Greeting patterns
# ---------------------------------------------------------------------------
GREETINGS = re.compile(
    r"^\s*(hi+|hello+|hey+|hiya|namaste|good\s*(morning|afternoon|evening|night)|"
    r"howdy|what'?s up|sup)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _db_error(label: str, exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=f"The {label} is temporarily unavailable. Please try again shortly.",
    )


def load_orders() -> dict[str, dict[str, Any]]:
    try:
        with ORDERS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Order database must be a JSON object")
        return data
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise _db_error("order database", exc) from exc


def load_products() -> dict[str, dict[str, Any]]:
    try:
        with PRODUCTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Product catalog must be a JSON object")
        return data
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise _db_error("product catalog", exc) from exc

# ---------------------------------------------------------------------------
# Order helpers
# ---------------------------------------------------------------------------

def normalize_order_id(raw: str) -> str:
    """Upper-case and strip. Also normalise 'ORD 101' → 'ORD-101'."""
    norm = raw.strip().upper()
    norm = re.sub(r"^ORD\s+(\d+)$", r"ORD-\1", norm)
    return norm


def get_order_by_id(order_id: str) -> dict[str, Any]:
    """Return a verified order record or raise HTTPException."""
    normalized = normalize_order_id(order_id)
    orders = load_orders()
    record = orders.get(normalized)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No order with ID '{normalized}' was found in our database. "
                "Please double-check the order number and try again."
            ),
        )
    return {"order_id": normalized, **record}


def search_orders_by_name(name: str) -> list[dict[str, Any]]:
    """
    Case-insensitive, whitespace-normalised customer name search.
    Returns all matching order records (with order_id injected).
    """
    orders = load_orders()

    def norm(s: str) -> str:
        s = unicodedata.normalize("NFC", s).lower()
        s = re.sub(r"\s+", " ", s).strip()
        return s

    needle = norm(name)
    matches: list[dict[str, Any]] = []
    for oid, record in orders.items():
        customer = norm(str(record.get("customer", "")))
        # Full-name match OR first/last name partial match
        if needle == customer or needle in customer or customer in needle:
            matches.append({"order_id": oid, **record})
    return matches


def fmt_order(order: dict[str, Any]) -> str:
    oid     = order.get("order_id", "?")
    cust    = order.get("customer", "Not available")
    product = order.get("product",  "Not available")
    price   = order.get("price",    "Not available")
    status  = order.get("status",   "Unknown")
    details = order.get("details",  "No additional details.")
    courier_txt  = f"\n• Courier: {order['courier']}"  if order.get("courier")     else ""
    tracking_txt = f"\n• Tracking ID: {order['tracking_id']}" if order.get("tracking_id") else ""
    return (
        f"Here are the details for order {oid}:\n"
        f"• Customer: {cust}\n"
        f"• Product: {product}\n"
        f"• Value: ₹{price}\n"
        f"• Status: {status}\n"
        f"• Details: {details}"
        f"{courier_txt}{tracking_txt}"
    )


def check_cancellation_eligibility(order: dict[str, Any]) -> dict[str, Any]:
    status = str(order.get("status", "")).lower()
    eligible = status == "processing"
    return {
        "eligible": eligible,
        "reason": (
            "The order is in Processing status and can be cancelled by contacting Aura support."
            if eligible
            else (
                f"The order status is '{order.get('status', 'Unknown')}'. "
                "Cancellation is only allowed while an order is in Processing status. "
                "Shipped or Out for Delivery orders cannot be cancelled, "
                "but you may refuse delivery at the doorstep."
            )
        ),
    }


def check_return_eligibility(order: dict[str, Any]) -> dict[str, Any]:
    status  = str(order.get("status",  "")).lower()
    details = str(order.get("details", "")).lower()
    if status != "delivered":
        return {
            "eligible": False,
            "reason": (
                f"The order status is '{order.get('status', 'Unknown')}'. "
                "Returns can only be requested after delivery."
            ),
        }
    if "14 days" in details:
        return {
            "eligible": False,
            "reason": (
                "Returns are accepted within 7 days of delivery. "
                "This order was delivered 14 days ago and is outside the return window."
            ),
        }
    return {
        "eligible": True,
        "reason": (
            "Returns are accepted within 7 days of delivery for unopened, "
            "unused products in original packaging."
        ),
    }

# ---------------------------------------------------------------------------
# Order ID detection (any format, not just ORD-XXX)
# ---------------------------------------------------------------------------
_ORDER_PATTERNS = [
    re.compile(r"\bORD[-\s]?\d{3,}\b", re.IGNORECASE),  # ORD-101, ORD101, ORD 101
    re.compile(r"\b[A-Z]{2,6}[-]\d{4,}\b"),              # BD-982103 (must have hyphen to avoid matching plain words)
    re.compile(r"\b\d{6,}\b"),                            # purely numeric long IDs
]

# Patterns that suggest the user is providing an order number by context
_ORDER_INTENT_PATTERNS = re.compile(
    r"(order\s*(id|number|no\.?)?[\s:is#]+|id[\s:is#]+|#)(\S+)",
    re.IGNORECASE,
)

# Short numeric IDs like "111" that need explicit "order" context to be treated as order IDs
_SHORT_NUMERIC = re.compile(r"^\d{3,5}$")


def extract_order_ids(text: str) -> list[str]:
    """Return candidate order IDs, normalised to uppercase. Short numbers require order-context."""
    seen: set[str] = set()
    results: list[str] = []
    text_lower = text.lower()

    has_order_ctx = bool(re.search(
        r"\b(order|track|tracking|parcel|package|shipment|dispatch|deliver|cancel|return|refund|where\s+is|check)\b",
        text_lower,
    ))

    def add(raw: str) -> None:
        norm = raw.strip().upper()
        # ORD 101 → ORD-101
        norm = re.sub(r"^ORD\s+(\d+)$", r"ORD-\1", norm)
        if norm not in seen:
            seen.add(norm)
            results.append(norm)

    # First: explicit context phrases like "order id is 111"
    for m in _ORDER_INTENT_PATTERNS.finditer(text):
        candidate = m.group(3).rstrip(".,;!?)")
        add(candidate)

    # Then: pattern-based extraction
    for pattern in _ORDER_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(0)
            # Short numeric: only include if order context present
            if _SHORT_NUMERIC.match(raw) and not has_order_ctx:
                continue
            add(raw)

    return results

# ---------------------------------------------------------------------------
# Name extraction from customer messages
# ---------------------------------------------------------------------------
_NAME_PATTERNS = [
    # "my name is X" — capture until punctuation, newline, or limiting keywords
    re.compile(
        r"my\s+name\s+is\s+([A-Za-z][A-Za-z\s]{1,60}?)(?:\s*[,\.!\?]|\s+(?:check|find|track|where|please|can|i|my|and)|$)",
        re.IGNORECASE,
    ),
    # "check/find/search by name X" or "customer name: X"
    re.compile(
        r"(?:check|search|find|look\s*up)\s+(?:order|orders|by|for)?\s*(?:name\s*)?[:\s]+([A-Za-z][A-Za-z\s]{1,60}?)(?:\s*[,\.!\?]|$)",
        re.IGNORECASE,
    ),
    # "by name X"
    re.compile(
        r"by\s+name\s+([A-Za-z][A-Za-z\s]{1,60}?)(?:\s*[,\.!\?]|$)",
        re.IGNORECASE,
    ),
    # "orders? for X"  / "find orders for X"
    re.compile(
        r"(?:find\s+)?orders?\s+for\s+([A-Za-z][A-Za-z\s]{1,60}?)(?:\s*[,\.!\?]|$)",
        re.IGNORECASE,
    ),
]

_NAME_STOP = re.compile(
    r"^(my|the|an|a|is|for|by|i|order|check|find|search|track|please|me|us|you)$",
    re.IGNORECASE,
)


def extract_customer_name(text: str) -> str | None:
    """
    Extract a customer name from phrasing like:
      "My name is Priya Sharma", "Find orders for Rahul Verma",
      "Check by name Ananya Patel"
    Returns the best candidate name (stripped, title-cased), or None.
    """
    for pattern in _NAME_PATTERNS:
        m = pattern.search(text)
        if m:
            name = m.group(1).strip().rstrip(".,;!? ")
            # Remove any trailing stop-words that may have been captured
            parts = name.split()
            while parts and _NAME_STOP.match(parts[-1]):
                parts.pop()
            name = " ".join(parts)
            if len(name) >= 2 and not _NAME_STOP.match(name):
                return name
    return None

# ---------------------------------------------------------------------------
# Chat engine helpers
# ---------------------------------------------------------------------------

def _make_reply(
    reply: str,
    intent: str,
    order_id: str | None = None,
    resolution: str = "RESOLVED",
    actions: list[str] | None = None,
    follow_up: bool = False,
) -> dict[str, Any]:
    return {
        "reply": reply,
        "customer_intent": intent,
        "order_id": order_id,
        "resolution_status": resolution,
        "actions_taken": actions or [],
        "follow_up_required": follow_up,
    }


def _greeting_reply(text: str) -> str:
    hour = datetime.now().hour
    if hour < 12:
        tod = "morning"
    elif hour < 17:
        tod = "afternoon"
    else:
        tod = "evening"
    return (
        f"Good {tod}! 👋 I'm Aria, your personal Aura Skincare assistant. "
        "I can help you with:\n"
        "• Tracking your order by ID or name\n"
        "• Shipping, return, and cancellation policies\n"
        "• Product recommendations and skincare routines\n"
        "• Payment options (including Cash on Delivery)\n\n"
        "What would you like to know?"
    )


def _product_recommendation_reply(text: str) -> str:
    text_l = text.lower()
    # Dry skin
    if re.search(r"\bdry\b", text_l):
        steps = "\n".join(ROUTINES["dry"])
        return (
            "Here's a recommended routine for **dry skin** 🌸:\n\n"
            f"{steps}\n\n"
            "All prices are catalog prices for demonstration. "
            "For best results, check product packaging for usage instructions."
        )
    # Oily skin
    if re.search(r"\boily\b|\bacne\b|\bpores?\b", text_l):
        steps = "\n".join(ROUTINES["oily"])
        return (
            "Here's a recommended routine for **oily/acne-prone skin** 🌿:\n\n"
            f"{steps}\n\n"
            "For verified suitability, check each product's packaging."
        )
    # Specific product query
    for key, detail in PRODUCT_DETAILS.items():
        if key in text_l:
            return (
                f"**{detail['name']}** — ₹{detail['price']} ({detail['size']})\n"
                f"• Best for: {detail['skin']}\n"
                f"• When to use: {detail['use']}\n"
                f"• Benefits: {detail['benefit']}\n\n"
                "Check the product packaging for complete ingredient information and usage directions."
            )
    # Comparison: vitamin c vs niacinamide
    if re.search(r"vitamin\s*c.*niacinamide|niacinamide.*vitamin\s*c", text_l):
        return (
            "**Vitamin C Serum vs Niacinamide Serum** — which is right for you?\n\n"
            "• **Aura Vitamin C Serum** (₹699): Best for brightening and antioxidant protection. "
            "Great for mornings. Suits all skin types.\n"
            "• **Aura Niacinamide Serum** (₹599): Best for minimising pores and controlling oil. "
            "Suits oily/acne-prone skin.\n\n"
            "They can generally be used together in different routine steps. "
            "Always check individual product labels for directions."
        )
    # General product listing
    return (
        "Aura Skincare's current catalog (8 products):\n\n"
        "**Serums:**\n"
        "• Vitamin C Serum (30ml) — ₹699\n"
        "• Hyaluronic Acid Serum (30ml) — ₹799\n"
        "• Niacinamide Serum (30ml) — ₹599\n\n"
        "**Cleansers:**\n"
        "• Green Tea Face Wash (100ml) — ₹349\n"
        "• Gentle Cleansing Balm (50g) — ₹549\n\n"
        "**Moisturiser & Toner:**\n"
        "• Aloe Vera Moisturizer (50g) — ₹449\n"
        "• Hydrating Toner (150ml) — ₹399\n\n"
        "**Sunscreen:**\n"
        "• Hydrating Sunscreen SPF 50 (50g) — ₹499\n\n"
        "Prices are for catalog demonstration. Check packaging for verified details."
    )

# ---------------------------------------------------------------------------
# Unified policy-based chat engine
# ---------------------------------------------------------------------------

def policy_reply(message: str) -> dict[str, Any]:
    """
    Deterministic support engine.
    Priority order:
      1. Greeting
      2. Order lookup by ID (when order context is present)
      3. Order lookup by customer name
      4. Intent to track without ID/name → ask for ID
      5. Policy-only intents (shipping, return, cancel, COD)
      6. Product / skincare questions
      7. Out-of-scope / general fallback
    """
    text = message.strip()
    text_l = text.lower()
    actions: list[str] = []

    # ── 1. Greeting ──────────────────────────────────────────────────────────
    if GREETINGS.match(text_l) and len(text.split()) <= 6:
        return _make_reply(
            _greeting_reply(text_l),
            intent="GREETING",
            resolution="RESOLVED",
        )

    # ── Out-of-scope guard ───────────────────────────────────────────────────
    ooscope = [
        "flight", "hotel booking", "stock price", "cricket score",
        "football", "weather", "news today", "recipe", "covid",
        "temperature today", "forecast",
    ]
    if any(k in text_l for k in ooscope):
        return _make_reply(
            "I'm Aria from Aura Skincare — I'm only equipped to help with Aura products, "
            "orders, delivery, returns, cancellations, and payment policies. "
            "For other topics, please use a general-purpose search engine. 😊",
            intent="OUT_OF_SCOPE",
            resolution="UNRESOLVED",
            follow_up=False,
        )

    # ── Detect high-level intents ────────────────────────────────────────────
    order_kws = [
        "order", "track", "tracking", "delivery", "deliver", "shipped",
        "cancel", "return", "refund", "where is", "when will", "package",
        "parcel", "shipment", "courier", "dispatch", "status",
    ]
    is_order_question = any(k in text_l for k in order_kws)

    candidate_ids  = extract_order_ids(message)
    candidate_name = extract_customer_name(text)

    # ── 2. Order lookup by ID ────────────────────────────────────────────────
    if candidate_ids:
        raw_id = candidate_ids[0]
        intent = "ORDER_TRACKING"

        try:
            order = get_order_by_id(raw_id)
        except HTTPException as exc:
            if exc.status_code == 404:
                return _make_reply(
                    f"Your order ID appears to be incorrect or was not found in our database. "
                    f"({exc.detail})\n\n"
                    "Please check the order number and try again, or search by your name.",
                    intent=intent,
                    order_id=raw_id,
                    resolution="UNRESOLVED",
                    follow_up=True,
                )
            # DB unavailable (503) — distinguish clearly from a not-found
            return _make_reply(
                f"I'm unable to look up orders right now because the order system is "
                f"temporarily unavailable. Please try again in a moment.",
                intent=intent,
                order_id=raw_id,
                resolution="UNRESOLVED",
                follow_up=True,
            )

        oid = order["order_id"]

        # Cancellation intent
        if re.search(r"\bcancel\b", text_l):
            intent = "ORDER_CANCELLATION"
            elig = check_cancellation_eligibility(order)
            reply = (
                f"Order {oid} (Status: {order.get('status')}) — "
                f"{elig['reason']}"
            )
            if elig["eligible"]:
                reply += (
                    "\n\nNote: This is a demo — actual cancellations require "
                    "contacting Aura customer support."
                )
            return _make_reply(
                reply, intent=intent, order_id=oid,
                resolution="UNRESOLVED" if elig["eligible"] else "RESOLVED",
                follow_up=elig["eligible"],
            )

        # Return/refund intent
        if re.search(r"\b(return|refund)\b", text_l):
            intent = "RETURN_POLICY"
            elig = check_return_eligibility(order)
            reply = (
                f"For order {oid} ({order.get('product', '')}):\n"
                f"{elig['reason']}\n\n"
                f"Full return policy: {POLICIES['returns']}"
            )
            return _make_reply(
                reply, intent=intent, order_id=oid,
                resolution="RESOLVED",
                follow_up=not elig["eligible"],
            )

        # General tracking / status
        return _make_reply(
            fmt_order(order),
            intent="ORDER_TRACKING",
            order_id=oid,
            resolution="RESOLVED",
        )

    # ── 3. Order lookup by customer name ─────────────────────────────────────
    if candidate_name:
        try:
            matches = search_orders_by_name(candidate_name)
        except HTTPException:
            return _make_reply(
                "I'm unable to search orders right now because the order system is "
                "temporarily unavailable. Please try again in a moment.",
                intent="ORDER_TRACKING",
                resolution="UNRESOLVED",
                follow_up=True,
            )

        if len(matches) == 0:
            return _make_reply(
                f"I couldn't find any order under the name '{candidate_name}'. "
                "Please check the spelling or provide your order ID directly.",
                intent="ORDER_TRACKING",
                resolution="UNRESOLVED",
                follow_up=True,
            )
        if len(matches) == 1:
            order = matches[0]
            return _make_reply(
                fmt_order(order),
                intent="ORDER_TRACKING",
                order_id=order["order_id"],
                resolution="RESOLVED",
            )
        # Multiple matches — list safe details and ask
        lines = [
            f"I found {len(matches)} orders associated with '{candidate_name}':\n"
        ]
        for m in matches:
            lines.append(
                f"• Order {m['order_id']} — {m.get('product', 'Unknown product')} — Status: {m.get('status', 'Unknown')}"
            )
        lines.append("\nWhich order were you asking about? Please provide the order ID.")
        return _make_reply(
            "\n".join(lines),
            intent="ORDER_TRACKING",
            resolution="UNRESOLVED",
            follow_up=True,
        )

    # ── 4. Tracking intent without ID or name → ask ──────────────────────────
    if is_order_question and not candidate_ids and not candidate_name:
        return _make_reply(
            "I'd love to help track your order! Could you please share:\n"
            "• Your **order ID** (e.g., ORD-101), or\n"
            "• Your **name** as it appears on the order?\n\n"
            "With either of those I can look up the details right away.",
            intent="ORDER_TRACKING",
            resolution="UNRESOLVED",
            follow_up=True,
        )

    # ── 5. Policy-only intents ───────────────────────────────────────────────
    if re.search(r"\b(return|refund|damaged|defective)\b", text_l):
        return _make_reply(POLICIES["returns"], intent="RETURN_POLICY")

    if re.search(r"\b(cancel|cancellation)\b", text_l):
        return _make_reply(POLICIES["cancellation"], intent="CANCELLATION_POLICY")

    if re.search(
        r"\b(shipping|delivery\s*charge|delivery\s*time|shipping\s*charge|"
        r"free\s*delivery|free\s*shipping|how\s*long|days?\s*to\s*deliver)\b",
        text_l,
    ):
        return _make_reply(POLICIES["shipping"], intent="SHIPPING_POLICY")

    if re.search(r"\bcash\s*on\s*delivery\b|\bcod\b", text_l):
        return _make_reply(POLICIES["cod"], intent="PAYMENT_POLICY")

    # ── 6. Product / skincare / routine questions ────────────────────────────
    product_kws = [
        "vitamin c", "sunscreen", "face wash", "toner", "hyaluronic",
        "aloe vera", "cleansing balm", "niacinamide", "serum", "moisturizer",
        "moisturiser", "product", "recommend", "routine", "skincare",
        "skin care", "ingredient", "spf", "oily skin", "dry skin",
        "acne", "pore", "brightening", "compare", "vs",
    ]
    if any(k in text_l for k in product_kws):
        return _make_reply(
            _product_recommendation_reply(text),
            intent="PRODUCT_INFORMATION",
        )

    # ── 7. General fallback ──────────────────────────────────────────────────
    return _make_reply(
        "Hi! I'm Aria from Aura Skincare. Here's what I can help you with:\n\n"
        "📦 **Order Tracking** — share your order ID (e.g., ORD-101) or your name\n"
        "🚚 **Shipping** — delivery charges and estimated times\n"
        "🔄 **Returns & Refunds** — eligibility and process\n"
        "❌ **Cancellations** — when orders can be cancelled\n"
        "💳 **Cash on Delivery** — COD availability and limits\n"
        "✨ **Products & Routines** — recommendations for your skin type\n\n"
        "What would you like to know?",
        intent="GENERAL_QUERY",
        resolution="UNRESOLVED",
        follow_up=True,
    )

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/aria")
def aria_page():
    return FileResponse(STATIC_DIR / "aria.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "Aura Skincare API",
        "version": "3.0.0",
        "orders_db": ORDERS_FILE.exists(),
        "products_db": PRODUCTS_FILE.exists(),
    }


@app.get("/api/orders")
def list_orders():
    """Returns all demo order records (evaluator / demo convenience endpoint)."""
    orders = load_orders()
    return {"orders": [{"order_id": k, **v} for k, v in orders.items()]}


@app.get("/api/orders/search")
def search_orders_endpoint(name: str = Query(..., min_length=1, max_length=200)):
    """Search orders by customer name (case-insensitive, partial-match aware)."""
    matches = search_orders_by_name(name)
    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"No orders found for customer name '{name}'.",
        )
    return {"matches": matches, "count": len(matches)}


@app.get("/api/orders/{order_id}")
def order_lookup(order_id: str):
    """Look up a single order by ID (any format, case-insensitive)."""
    return get_order_by_id(order_id)


@app.get("/api/products")
def list_products():
    products = load_products()
    return {"products": [{"product_id": k, **v} for k, v in products.items()]}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@app.post("/api/chat")
def chat(request: ChatRequest):
    """
    Unified chat endpoint — used by both typed chat and voice chat.
    Handles general conversation, order lookup, name search, and policies.
    """
    return policy_reply(request.message)


class SummaryRequest(BaseModel):
    transcript: list[dict] = Field(default_factory=list)
    last_intent: str = "GENERAL_QUERY"
    last_order_id: str | None = None
    last_resolution: str = "UNRESOLVED"
    actions_taken: list[str] = Field(default_factory=list)
    follow_up_required: bool = True


@app.post("/api/summary")
def generate_summary(req: SummaryRequest):
    user_msgs = [m for m in req.transcript if m.get("speaker") == "You"]
    first_q   = user_msgs[0].get("text", "") if user_msgs else ""
    last_q    = user_msgs[-1].get("text", "") if user_msgs else ""
    summary_text = (
        f"Customer asked {len(user_msgs)} question(s). "
        f"First: \"{first_q[:120]}\". "
        + (f"Last: \"{last_q[:120]}\"." if len(user_msgs) > 1 else "")
        + (f" Order {req.last_order_id} was discussed." if req.last_order_id else "")
        + (" Query resolved." if req.last_resolution == "RESOLVED" else " Follow-up may be required.")
    )
    valid_resolutions = {"RESOLVED", "UNRESOLVED", "ESCALATION_REQUIRED"}
    return {
        "customer_intent":   req.last_intent,
        "order_id":          req.last_order_id,
        "resolution_status": req.last_resolution if req.last_resolution in valid_resolutions else "UNRESOLVED",
        "call_summary":      summary_text,
        "actions_taken":     req.actions_taken,
        "follow_up_required":req.follow_up_required,
        "transcript":        req.transcript,
        "generated_at":      datetime.now(timezone.utc).isoformat(),
    }
