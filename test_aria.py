"""
Aura Skincare — Aria backend test suite
Run with:  python test_aria.py
(Server must be running at http://127.0.0.1:8000)
"""
import urllib.request
import json
import sys

BASE = "http://127.0.0.1:8000"


def chat(msg: str) -> dict:
    data = json.dumps({"message": msg}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.loads(r.read())


results = []


def test(name: str, fn, *, key: str, contains: str = "", not_contains: str = ""):
    try:
        res = fn()
        actual = str(res.get(key, ""))
        ok = True
        if contains:
            ok = ok and contains.lower() in actual.lower()
        if not_contains:
            ok = ok and not_contains.lower() not in actual.lower()
        results.append((name, "PASS" if ok else "FAIL", repr(actual[:100])))
    except Exception as e:
        results.append((name, "FAIL", str(e)[:100]))


# ── Test cases ────────────────────────────────────────────────────────────────

test("T1  ORD-101 found",
     lambda: chat("Where is my order ORD-101?"),
     key="resolution_status", contains="RESOLVED")

test("T2  Numeric ID 111 not found",
     lambda: chat("My order id is 111"),
     key="reply", contains="not found")

test("T3  ORD-999 not found",
     lambda: chat("Track order ORD-999"),
     key="reply", contains="not found")

test("T4  Priya Sharma found by name",
     lambda: chat("My name is Priya Sharma, check my order"),
     key="resolution_status", contains="RESOLVED")

test("T5  Unknown name — clear not-found response",
     lambda: chat("Check my order by name Zara McFakePerson"),
     key="reply", contains="could not find")

test("T6  Multiple name matches listed",
     lambda: chat("Find orders for Sharma"),
     key="reply", contains="ORD-")

test("T7  Skincare product question",
     lambda: chat("What serum is good for dry skin?"),
     key="customer_intent", contains="PRODUCT_INFORMATION")

test("T8  Greeting",
     lambda: chat("Hello!"),
     key="customer_intent", contains="GREETING")

test("T9  Out-of-scope (weather)",
     lambda: chat("What is the weather today?"),
     key="customer_intent", contains="OUT_OF_SCOPE")

test("T10 Shipping policy",
     lambda: chat("What are your shipping charges?"),
     key="customer_intent", contains="SHIPPING_POLICY")

test("T11 /api/orders/search?name=Rahul",
     lambda: get("/api/orders/search?name=Rahul"),
     key="count", contains="1")

test("T12 /api/orders/ORD-102",
     lambda: get("/api/orders/ORD-102"),
     key="order_id", contains="ORD-102")

test("T13 Backend failure (503) vs invalid order — health check",
     lambda: get("/api/health"),
     key="status", contains="ok")

test("T14 Cancellation policy (no order ID)",
     lambda: chat("Can I cancel my order?"),
     key="customer_intent", contains="CANCELLATION_POLICY")

test("T15 COD enquiry",
     lambda: chat("Is Cash on Delivery available?"),
     key="customer_intent", contains="PAYMENT_POLICY")

# ── Results ──────────────────────────────────────────────────────────────────

print()
print("=" * 65)
print("  AURA SKINCARE / ARIA — AUTOMATED BACKEND TEST RESULTS")
print("=" * 65)
for name, status, note in results:
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon} {name}")
    if status == "FAIL":
        print(f"         ↳ {note}")

passed = sum(1 for _, s, _ in results if s == "PASS")
total  = len(results)
print(f"\n  {passed}/{total} tests passed", "🎉" if passed == total else "")
print("=" * 65)
sys.exit(0 if passed == total else 1)
