from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import schemas, crud
from ..database import get_db

router = APIRouter()

@router.post("/simulation/trigger-email")
def trigger_email(data: schemas.SimulationTrigger, db: Session = Depends(get_db)):
    """
    Entry point for the simulation. 
    Instead of processing immediately, it drops an event into the ledger.
    The autonomous agent will pick this up.
    """
    # Create the event
    event = crud.create_event(
        db, 
        event_type="INVOICE_RECEIVED", 
        payload=data.dict()
    )
    
    return {
        "status": "Event queued", 
        "event_id": event.id, 
        "message": "The autonomous agent will process this invoice shortly."
    }
