import logging

logger = logging.getLogger("Notifications")

def send_sms_to_owner(message: str):
    """
    Simulates sending an SMS to the shop owner.
    In a real app, this would use Twilio or AWS SNS.
    """
    recipient = "+91 9876543210" # Placeholder owner number
    logger.info(f"📱 [SMS SENT] To: {recipient} | Message: {message}")
    print(f"\n--- SMS NOTIFICATION ---\nTo: {recipient}\nMessage: {message}\n------------------------\n")
    return True

def send_email_to_supplier(vendor_email: str, item_name: str, quantity: int):
    """
    Simulates sending a restock order email to a supplier.
    In a real app, this would use SendGrid or SMTP.
    """
    subject = f"PURCHASE ORDER: Restock for {item_name}"
    body = f"Hello,\n\nPlease supply {quantity} units of {item_name} at your earliest convenience.\n\nRegards,\nProcureIQ Autonomous Agent"
    
    logger.info(f"📧 [EMAIL SENT] To: {vendor_email} | Subject: {subject}")
    print(f"\n--- EMAIL NOTIFICATION ---\nTo: {vendor_email}\nSubject: {subject}\nBody:\n{body}\n--------------------------\n")
    return True
