"""
Severity Engine — Pure Logic Module

Calculates system operating state based on stock levels, supplier status,
and AI confidence. Contains ZERO database calls or external dependencies.

Part of the Decision Intelligence Layer extension.
"""


def calculate_system_state(
    stock_quantity: int,
    reorder_level: int,
    supplier_status: str,
    ai_confidence: float,
) -> dict:
    """
    Calculate system severity score and operating mode.

    Args:
        stock_quantity:   Current stock level of the most critical item
        reorder_level:   Reorder threshold for that item
        supplier_status: "AVAILABLE" or "UNAVAILABLE"
        ai_confidence:   AI match confidence (0–100)

    Returns:
        {"severity_score": int (0–10), "mode": "DEBATE"|"CRISIS"|"SAFE"}
    """

    # ── Rule 1: Low AI confidence → SAFE mode immediately ──────────────
    if ai_confidence < 60:
        return {"severity_score": 0, "mode": "SAFE"}

    # ── Rule 2: Base severity from stock level ─────────────────────────
    if stock_quantity <= 0:
        severity = 9
    elif stock_quantity <= reorder_level:
        severity = 6
    else:
        severity = 2

    # ── Rule 3: Supplier unavailable adds +2 ───────────────────────────
    if supplier_status == "UNAVAILABLE":
        severity += 2

    # ── Rule 4: Cap at 10 ──────────────────────────────────────────────
    severity = min(severity, 10)

    # ── Rule 5: Mode assignment ────────────────────────────────────────
    if severity >= 7:
        mode = "CRISIS"
    else:
        mode = "DEBATE"

    return {"severity_score": severity, "mode": mode}
