"""
Database retry decorators for handling SQLite concurrent write locking.
"""
import time
import logging
from functools import wraps
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

def retry_on_db_lock(max_retries=3, delay=0.5):
    """
    Decorator that retries database operations on 'database is locked' errors.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        delay: Delay in seconds between retries (default: 0.5)
    
    Usage:
        @retry_on_db_lock(max_retries=3, delay=0.5)
        def my_db_write_function(db, data):
            db.add(data)
            db.commit()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    last_exception = e
                    if "database is locked" in str(e).lower():
                        if attempt < max_retries:
                            logger.warning(
                                f"Database locked on {func.__name__}, "
                                f"retry {attempt + 1}/{max_retries} in {delay}s"
                            )
                            time.sleep(delay)
                            continue
                    # Not a lock error or max retries reached
                    raise
            
            # Max retries exceeded
            logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
            raise last_exception
        
        return wrapper
    return decorator
