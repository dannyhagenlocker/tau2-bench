"""Human-readable gloss for cluster / DB-diff signatures (retail domain).

Turns machine signatures like
    missed:orders.*.cancel_reason;missed:orders.*.return_items;missed:orders.*.status
into a glance-readable phrase like
    "missing: cancel order, return items"

by mapping the *set* of changed DB fields to the retail action that produces
them and the divergence kind to a verb. Purely presentational — the raw
signature remains the source of truth for clustering.
"""

from __future__ import annotations

_KIND_VERB = {"missed": "missing", "wrong": "wrong", "extra": "extra"}


def _norm(pattern: str) -> str:
    """orders.*.items[].options.* -> orders.items.options"""
    parts = []
    for p in pattern.split("."):
        p = p.replace("[]", "")
        if p and p != "*":
            parts.append(p)
    return ".".join(parts)


def _actions_from_fields(fields: set[str]) -> list[str]:
    """Map a set of normalized field paths to the retail actions behind them.

    Matches on exact path *components* (e.g. the field `orders.return_items`
    has components {orders, return_items}), so `return_items` / `exchange_items`
    don't spuriously trigger the `items` (modify) action.
    """
    comps: set[str] = set()
    order_addr = user_addr = False
    for f in fields:
        toks = f.split(".")
        comps.update(toks)
        if "address" in toks:
            if f.startswith("orders."):
                order_addr = True
            elif f.startswith("users."):
                user_addr = True

    acts: list[str] = []
    if "cancel_reason" in comps:
        acts.append("cancel order")
    if "return_items" in comps or "return_payment_method_id" in comps:
        acts.append("return items")
    if comps & {
        "exchange_items",
        "exchange_new_items",
        "exchange_payment_method_id",
        "exchange_price_difference",
    }:
        acts.append("exchange items")
    if "items" in comps:  # items[].item_id / price / options
        acts.append("modify order items")
    if order_addr:
        acts.append("change order address")
    if user_addr:
        acts.append("change user address")
    if "payment_methods" in comps and "balance" in comps:
        acts.append("gift-card balance")
    elif "payment_methods" in comps:
        acts.append("modify payment method")

    if not acts:
        # supporting-only fields, or something unmapped: fall back gracefully
        if "payment_history" in comps:
            acts.append("order payment/refund")
        elif "status" in comps:
            acts.append("order status")
        else:
            acts.append(", ".join(sorted({f.split(".")[-1] for f in fields})))

    out: list[str] = []
    for a in acts:
        if a not in out:
            out.append(a)
    return out


def gloss_db_signature(signature: str | None) -> str:
    if not signature or signature == "no_db_diff":
        return ""
    by_kind: dict[str, set[str]] = {}
    for item in signature.split(";"):
        if ":" not in item:
            continue
        kind, pattern = item.split(":", 1)
        by_kind.setdefault(kind, set()).add(_norm(pattern))

    parts = []
    for kind in ("missed", "wrong", "extra"):
        if kind not in by_kind:
            continue
        acts = _actions_from_fields(by_kind[kind])
        parts.append(f"{_KIND_VERB.get(kind, kind)}: {', '.join(acts)}")
    return " · ".join(parts)


def gloss_cluster_signature(signature: str | None) -> str:
    """Gloss a cluster-level signature (`db=… | nl=… | chain=…`)."""
    if not signature:
        return ""
    out = []
    for part in signature.split(" | "):
        if part.startswith("db="):
            g = gloss_db_signature(part[3:])
            if g:
                out.append(g)
        elif part.startswith("nl="):
            out.append("says: " + part[3:])
        elif part.startswith("chain="):
            out.append("tools: " + part[6:].replace("->", " → "))
        else:
            out.append(part)
    return " | ".join(out)
