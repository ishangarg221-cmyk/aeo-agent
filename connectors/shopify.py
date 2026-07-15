"""
Read-only Shopify connector.
============================
SAFETY BY CONSTRUCTION: this module exposes ONLY GET calls. There is no method
here that can create, update, delete, or publish anything. The daily agent
therefore cannot change the store even if asked to — writes are an APPROVE step
you do yourself in Shopify admin.

Auth (set in the environment, never in code):
    SHOPIFY_STORE         e.g. "myna-store"  (the *.myshopify.com handle)
    SHOPIFY_ADMIN_TOKEN   Admin API access token with read_orders, read_products
    SHOPIFY_API_VERSION   optional, defaults to a recent stable version
"""
from __future__ import annotations
import datetime as dt
import os

try:
    import requests
except ImportError:
    requests = None

API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-01")


class ShopifyReadOnly:
    def __init__(self):
        self.store = os.getenv("SHOPIFY_STORE", "").strip()
        self.token = os.getenv("SHOPIFY_ADMIN_TOKEN", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.store and self.token and requests)

    def _get(self, path: str, params: dict | None = None):
        url = f"https://{self.store}.myshopify.com/admin/api/{API_VERSION}/{path}"
        try:
            r = requests.get(url, headers={"X-Shopify-Access-Token": self.token},
                             params=params or {}, timeout=30)
            if r.status_code == 200:
                return r.json()
            return {"_error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"_error": str(e)}

    # ---- read-only reports -------------------------------------------------
    def sales_yesterday(self) -> dict:
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        until = since + dt.timedelta(days=1)
        data = self._get("orders.json", {
            "status": "any", "created_at_min": since.isoformat(),
            "created_at_max": until.isoformat(), "limit": 250,
            "fields": "id,total_price,currency,financial_status,line_items"})
        if "_error" in data:
            return data
        orders = data.get("orders", [])
        revenue = sum(float(o.get("total_price", 0) or 0) for o in orders)
        units = sum(sum(li.get("quantity", 0) for li in o.get("line_items", []))
                    for o in orders)
        cur = orders[0].get("currency", "INR") if orders else "INR"
        return {"orders": len(orders), "revenue": round(revenue, 2),
                "units": units, "currency": cur}

    def low_stock(self, threshold: int = 5) -> list[dict]:
        data = self._get("products.json", {
            "limit": 250, "fields": "id,title,variants,status"})
        if "_error" in data:
            return [{"_error": data["_error"]}]
        low = []
        for p in data.get("products", []):
            if p.get("status") != "active":
                continue
            for v in p.get("variants", []):
                q = v.get("inventory_quantity")
                if isinstance(q, int) and q <= threshold:
                    low.append({"product": p["title"], "variant": v.get("title", ""),
                                "qty": q})
        return sorted(low, key=lambda x: x.get("qty", 0))

    def products_missing_schema_fields(self) -> list[dict]:
        """Flag active products with thin AEO metadata (no body/description)."""
        data = self._get("products.json", {
            "limit": 250, "fields": "id,title,handle,body_html,status,variants,image"})
        if "_error" in data:
            return [{"_error": data["_error"]}]
        flagged = []
        for p in data.get("products", []):
            if p.get("status") != "active":
                continue
            body = (p.get("body_html") or "").strip()
            if len(body) < 120:  # thin description → weak Product schema fodder
                flagged.append({"title": p["title"], "handle": p.get("handle", ""),
                                "reason": "thin/empty description — weak Product schema & AEO"})
        return flagged
