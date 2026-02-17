import imaplib
import email
import os
import logging
from email.header import decode_header
from typing import List, Dict

logger = logging.getLogger("EmailService")

class EmailIngestionService:
    def __init__(self):
        self.host = os.getenv("EMAIL_HOST")
        self.user = os.getenv("EMAIL_USER")
        self.password = os.getenv("EMAIL_PASS")
        self.port = int(os.getenv("EMAIL_PORT", 993))
        
    def _connect(self):
        try:
            mail = imaplib.IMAP4_SSL(self.host, self.port)
            mail.login(self.user, self.password)
            return mail
        except Exception as e:
            logger.error(f"Failed to connect to email: {str(e)}")
            return None

    def fetch_latest_invoices(self) -> List[Dict]:
        """
        Polls both INBOX and Junk/Spam folders for potential invoices.
        """
        mail = self._connect()
        if not mail:
            return []

        results = []
        # Folders to check (Standard IMAP and Gmail specific)
        folders = ["INBOX", "Spam", "[Gmail]/Spam", "Junk"]
        
        for folder in folders:
            try:
                status, _ = mail.select(folder)
                if status != 'OK':
                    continue
                
                # Search for unread emails (or just recent ones)
                # For hackathon demo, we check UNSEEN
                status, messages = mail.search(None, 'UNSEEN')
                if status != 'OK':
                    continue

                for num in messages[0].split():
                    status, data = mail.fetch(num, '(RFC822)')
                    if status != 'OK':
                        continue

                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))
                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                body = part.get_payload(decode=True).decode()
                    else:
                        body = msg.get_payload(decode=True).decode()

                    # Simple heuristic: Check if 'invoice' or 'bill' is in subject or body
                    if "invoice" in subject.lower() or "invoice" in body.lower():
                        logger.info(f"Found potential invoice in {folder}: {subject}")
                        results.append({
                            "subject": subject,
                            "body": body,
                            "from": msg.get("From"),
                            "date": msg.get("Date")
                        })
                        
                        # Mark as seen so we don't process it again (done by FETCH usually, but let's be explicit)
                        mail.store(num, '+FLAGS', '\\Seen')

            except Exception as e:
                logger.warning(f"Error checking folder {folder}: {str(e)}")
                continue

        mail.logout()
        return results
