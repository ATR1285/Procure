"""
Decision Engine — Three-Way Match Logic

ALL ERP data access goes through ERPAdapter.
NO direct db.query() calls to Vendor, VendorAlias, PO, or Receipt models.
"""

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from .. import models, crud
import logging

logger = logging.getLogger("DecisionEngine")

def calculate_confidence(raw_name: str, candidate_name: str) -> int:
    """
    Calculate vendor name match confidence score.
    
    Scoring Logic (Transparent & Deterministic):
    - Exact match: 100 points
    - Substring match: 85 points
    - Fuzzy match: 50 points (base)
    """
    n1 = raw_name.lower().strip()
    n2 = candidate_name.lower().strip()
    
    if n1 == n2:
        logger.debug(f"Exact match: '{raw_name}' == '{candidate_name}' -> 100")
        return 100
    
    if n1 in n2 or n2 in n1:
        logger.debug(f"Substring match: '{raw_name}' <-> '{candidate_name}' -> 85")
        return 85
    
    logger.debug(f"Fuzzy match: '{raw_name}' vs '{candidate_name}' -> 50")
    return 50

def calculate_three_way_confidence(vendor_match: bool, po_match: bool, receipt_exists: bool) -> int:
    """
    Three-way match confidence:
    - Vendor + PO + Receipt = 95%
    - Vendor + PO = 80%
    - Vendor only = 60%
    - No match = 30%
    """
    if vendor_match and po_match and receipt_exists:
        return 95
    elif vendor_match and po_match:
        return 80
    elif vendor_match:
        return 60
    return 30

def process_invoice_match(db: Session, payload: dict):
    """
    Three-Way Match — autonomous invoice processing.
    
    ALL ERP access goes through erp_adapter. Zero direct DB queries to ERP tables.
    
    Steps:
    1. Create/fetch invoice record
    2. Check vendor alias (via adapter) — LEARNING applies here
    3. AI vendor matching (via adapter for vendor list)
    4. PO + Receipt lookup (via adapter)
    5. Calculate confidence
    6. Set status for human review
    """
    from ..services.erp_adapter import erp_adapter
    
    invoice_number = payload.get("invoiceNumber")
    raw_vendor = payload.get("vendorName")
    amount = payload.get("invoiceAmount")
    raw_text = payload.get("raw_text")
    
    logger.info(f"[PROCESS] Analyzing invoice {invoice_number} | vendor='{raw_vendor}' | amount={amount}")
    
    # ── Step 1: Create invoice record ──────────────────────────
    invoice = db.query(models.Invoice).filter(models.Invoice.invoice_number == invoice_number).first()
    if not invoice:
        invoice = models.Invoice(
            invoice_number=invoice_number,
            total_amount=amount,
            status="PROCESSING",
            extracted_data={"raw_vendor": raw_vendor, "email_body": raw_text},
            audit_trail=[{"t": "received", "m": f"Source: {'Real Email' if raw_text else 'Simulation'}"}]
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)

    # ── Step 2: Check vendor alias via ERP Adapter (LEARNING) ──
    match_score = 0
    reasoning = ""
    target_vendor_id = None
    po_matched = False
    receipt_found = False
    
    # ALL alias lookups go through the adapter — NO direct DB query
    alias_result = erp_adapter.get_vendor_alias(raw_vendor)
    
    if alias_result:
        target_vendor_id = alias_result["vendor_id"]
        match_score = alias_result["confidence"]
        reasoning = f"Autonomous Match: Learned alias '{raw_vendor}' found in ontology (confidence={match_score}%)."
        logger.info(f"[LEARNING] Alias applied: '{raw_vendor}' → vendor_id={target_vendor_id}, confidence improved to {match_score}%")
    else:
        # ── Step 3: AI vendor matching ─────────────────────────
        # Get vendor list from ERP Adapter (NOT direct DB)
        known_vendors = erp_adapter.get_vendors()
        logger.info(f"[MATCH] ERP Adapter returned {len(known_vendors)} vendors for matching")
        
        from ..services.ai_service import analyze_invoice_with_ai
        import asyncio
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ai_result = loop.run_until_complete(analyze_invoice_with_ai(raw_vendor, amount, known_vendors, raw_text))
            loop.close()
            
            if raw_text:
                invoice.total_amount = ai_result.get("extracted_amount", invoice.total_amount)
                invoice.extracted_data["raw_vendor"] = ai_result.get("extracted_vendor", raw_vendor)
            
            match_score = ai_result.get("confidence", 0)
            reasoning = ai_result.get("reasoning", "AI Analysis failed to provide reasoning.")
            target_vendor_id = ai_result.get("best_match_id")
            
            logger.info(f"[AI] Analysis: vendor_id={target_vendor_id}, confidence={match_score}%, reasoning={reasoning}")
            
        except Exception as e:
            logger.error(f"[AI] Matcher Error: {str(e)}")
            match_score = 40
            reasoning = "AI Service unavailable or parsing error."

    # ── Step 4: Three-way match (PO + Receipt via adapter) ─────
    if target_vendor_id:
        try:
            pos = erp_adapter.get_purchase_orders(vendor_id=target_vendor_id)
            
            if pos:
                matching_po = None
                for po in pos:
                    if po.get("total_amount") and abs(po["total_amount"] - float(amount or 0)) < 0.01:
                        matching_po = po
                        break
                
                if not matching_po and pos:
                    matching_po = pos[0]
                
                if matching_po:
                    po_matched = True
                    invoice.audit_trail.append({
                        "t": "po_match",
                        "m": f"Matched PO: {matching_po.get('po_number', matching_po.get('id'))}"
                    })
                    
                    receipts = erp_adapter.get_goods_receipts(matching_po["id"])
                    if receipts:
                        receipt_found = True
                        invoice.audit_trail.append({
                            "t": "receipt_verified",
                            "m": f"Receipt confirmed: {len(receipts)} delivery record(s) found"
                        })
                    else:
                        invoice.audit_trail.append({
                            "t": "receipt_missing",
                            "m": "No goods receipt found for matched PO"
                        })
            
            three_way_score = calculate_three_way_confidence(
                vendor_match=target_vendor_id is not None,
                po_match=po_matched,
                receipt_exists=receipt_found
            )
            
            if three_way_score > match_score:
                reasoning += f" | Three-way match: vendor={bool(target_vendor_id)}, PO={po_matched}, receipt={receipt_found}"
                match_score = three_way_score
            
            logger.info(f"[THREE-WAY] vendor={bool(target_vendor_id)}, PO={po_matched}, receipt={receipt_found}, score={three_way_score}")
            
        except Exception as e:
            logger.error(f"[THREE-WAY] Error: {str(e)}")

    # ── Step 5: Decision ───────────────────────────────────────
    invoice.status = "PENDING_REVIEW"
    invoice.confidence_score = match_score
    invoice.reasoning_note = reasoning
    invoice.vendor_id = target_vendor_id
    
    invoice.audit_trail.append({
        "t": "match_attempt", 
        "score": match_score, 
        "note": reasoning
    })
    invoice.audit_trail.append({
        "t": "ready_for_review", 
        "m": f"Match confidence {match_score}%. Queued for owner review."
    })
    flag_modified(invoice, "audit_trail")
    flag_modified(invoice, "extracted_data")
    
    db.commit()
    
    logger.info(f"[DECISION] Invoice {invoice_number}: status={invoice.status}, confidence={match_score}%, vendor_id={target_vendor_id}")
