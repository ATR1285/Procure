"""
Gmail Invoice Checker - Optimized for Cron Automation

Minimal console output for cron-job.org compatibility.
Logs to file, stores to database, returns proper exit codes.

Usage:
    python gmail_checker.py           # Minimal output for cron
    python gmail_checker.py --verbose # Detailed output for testing
"""

import os
import sys
import json
import logging
import argparse
import sqlite3
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from app.services.email_service import EmailService

# Setup logging
def setup_logging(verbose=False):
    """Configure logging with file rotation."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create logger
    logger = logging.getLogger('gmail_checker')
    logger.setLevel(log_level)
    
    # File handler with rotation (5MB max)
    file_handler = RotatingFileHandler(
        'gmail_checker.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler (minimal for cron)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Database operations
class InvoiceDB:
    """SQLite database for storing invoices."""
    
    def __init__(self, db_path='gmail_invoices.db'):
        self.db_path = db_path
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Create database and table if not exists."""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_name TEXT,
                vendor_email TEXT,
                invoice_number TEXT UNIQUE,
                invoice_date TEXT,
                due_date TEXT,
                total_amount REAL,
                currency TEXT DEFAULT 'USD',
                line_items_json TEXT,
                found_in_spam INTEGER DEFAULT 0,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email_message_id TEXT UNIQUE
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_invoice_number 
            ON invoices(invoice_number)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_email_message_id 
            ON invoices(email_message_id)
        ''')
        
        self.conn.commit()
    
    def save_invoice(self, invoice_data, message_id, found_in_spam=False):
        """
        Save invoice to database.
        Returns (success: bool, duplicate: bool)
        """
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO invoices (
                    vendor_name, vendor_email, invoice_number,
                    invoice_date, due_date, total_amount, currency,
                    line_items_json, found_in_spam, email_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                invoice_data.get('vendor_name'),
                invoice_data.get('vendor_email'),
                invoice_data.get('invoice_number'),
                invoice_data.get('invoice_date'),
                invoice_data.get('due_date'),
                invoice_data.get('total_amount'),
                invoice_data.get('currency', 'USD'),
                json.dumps(invoice_data.get('line_items', [])),
                1 if found_in_spam else 0,
                message_id
            ))
            
            self.conn.commit()
            return (True, False)
            
        except sqlite3.IntegrityError:
            # Duplicate invoice_number or message_id
            return (False, True)
        except Exception as e:
            logging.getLogger('gmail_checker').error(f"DB save error: {e}")
            return (False, False)
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def process_emails(verbose=False):
    """
    Main email processing function.
    
    Returns:
        tuple: (exit_code, stats_dict)
    """
    logger = logging.getLogger('gmail_checker')
    stats = {
        'total_scanned': 0,
        'invoices_found': 0,
        'rescued_from_spam': 0,
        'duplicates_skipped': 0,
        'errors': 0
    }
    
    output_lines = 0
    MAX_OUTPUT_LINES = 50
    
    try:
        # Initialize services
        email_service = EmailService()
        db = InvoiceDB()
        
        logger.debug("Initializing Gmail API...")
        
        # Fetch emails from inbox and spam
        logger.debug("Fetching inbox emails...")
        inbox_emails = email_service.fetch_new_invoices(folder='INBOX')
        
        logger.debug("Fetching spam emails...")
        spam_emails = email_service.fetch_new_invoices(folder='SPAM')
        
        all_emails = [(email, False) for email in inbox_emails] + \
                     [(email, True) for email in spam_emails]
        
        stats['total_scanned'] = len(all_emails)
        
        if verbose:
            print(f"\nScanning {stats['total_scanned']} emails...")
            output_lines += 2
        
        # Process each email
        for email_data, is_spam in all_emails:
            if output_lines >= MAX_OUTPUT_LINES and not verbose:
                logger.warning("Output limit reached, remaining emails logged to file only")
                break
            
            message_id = email_data.get('id', 'unknown')
            subject = email_data.get('subject', 'No subject')
            sender = email_data.get('from', 'Unknown')
            
            logger.debug(f"Processing: {subject} from {sender}")
            
            try:
                # Extract invoice data (simulated - replace with actual extraction)
                invoice_data = extract_invoice_data(email_data, logger, verbose)
                
                if not invoice_data:
                    if verbose:
                        print(f"[SKIPPED] {subject[:50]}")
                        output_lines += 1
                    logger.info(f"Skipped non-invoice: {subject}")
                    continue
                
                # Save to database
                success, is_duplicate = db.save_invoice(
                    invoice_data,
                    message_id,
                    found_in_spam=is_spam
                )
                
                if is_duplicate:
                    stats['duplicates_skipped'] += 1
                    logger.info(f"Duplicate invoice: {invoice_data.get('invoice_number')}")
                    continue
                
                if success:
                    stats['invoices_found'] += 1
                    if is_spam:
                        stats['rescued_from_spam'] += 1
                    
                    # Minimal console output
                    vendor = invoice_data.get('vendor_name', 'Unknown')
                    amount = invoice_data.get('total_amount', 0)
                    inv_num = invoice_data.get('invoice_number', 'N/A')
                    
                    print(f"[INVOICE] {vendor} | ${amount} | {inv_num}")
                    output_lines += 1
                    
                    logger.info(f"Saved invoice #{inv_num} from {vendor}")
                else:
                    stats['errors'] += 1
                    logger.error(f"Failed to save invoice from {sender}")
                    
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error processing email {message_id}: {str(e)[:100]}")
                
                if output_lines < MAX_OUTPUT_LINES:
                    print(f"[ERROR] {str(e)[:50]}")
                    output_lines += 1
        
        # Final summary
        summary = (
            f"Scanned: {stats['total_scanned']} emails | "
            f"Found: {stats['invoices_found']} invoices | "
            f"Rescued from spam: {stats['rescued_from_spam']}"
        )
        print(f"\n{summary}")
        logger.info(summary)
        
        if stats['duplicates_skipped'] > 0:
            logger.info(f"Skipped {stats['duplicates_skipped']} duplicates")
        
        # Close database
        db.close()
        
        # Determine exit code
        if stats['errors'] > 0:
            logger.warning(f"{stats['errors']} errors occurred")
            return (2, stats)  # Warnings
        else:
            return (0, stats)  # Success
            
    except Exception as e:
        logger.critical(f"Critical error: {str(e)}")
        print(f"[ERROR] Critical failure - check gmail_checker.log")
        return (1, stats)  # Critical error


def extract_invoice_data(email_data, logger, verbose=False):
    """
    Extract invoice data from email.
    
    Returns dict with invoice fields or None if not an invoice.
    """
    subject = email_data.get('subject', '').lower()
    body = email_data.get('body', '')
    
    # Simple heuristic - enhance with actual AI extraction
    is_invoice = any(word in subject for word in ['invoice', 'bill', 'receipt', 'payment'])
    
    if not is_invoice:
        return None
    
    # Simulated extraction - replace with actual AI extraction logic
    invoice_data = {
        'vendor_name': email_data.get('from', 'Unknown').split('<')[0].strip(),
        'vendor_email': email_data.get('from', ''),
        'invoice_number': f"INV-{email_data.get('id', 'unknown')[:8]}",
        'invoice_date': email_data.get('date', datetime.now().isoformat()),
        'due_date': None,
        'total_amount': 0.0,  # Would extract from body
        'currency': 'USD',
        'line_items': []
    }
    
    if verbose:
        logger.debug(f"Extracted invoice: {invoice_data['invoice_number']}")
    
    return invoice_data


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Gmail Invoice Checker - Cron-optimized'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output for manual testing'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    logger.info("=" * 60)
    logger.info("Gmail Invoice Checker Started")
    logger.info(f"Verbose mode: {args.verbose}")
    logger.info("=" * 60)
    
    # Process emails
    exit_code, stats = process_emails(args.verbose)
    
    logger.info("=" * 60)
    logger.info(f"Completed with exit code {exit_code}")
    logger.info("=" * 60)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
