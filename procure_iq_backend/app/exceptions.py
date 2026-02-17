"""
Custom exception classes for ProcureIQ.

Provides structured error handling across the application.
"""

class ProcureIQException(Exception):
    """Base exception for all ProcureIQ errors."""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class AIServiceException(ProcureIQException):
    """Raised when AI service (Gemini/OpenAI/Ollama) fails."""
    pass


class EmailServiceException(ProcureIQException):
    """Raised when email service encounters errors."""
    pass


class DatabaseException(ProcureIQException):
    """Raised for database-related errors."""
    pass


class ValidationException(ProcureIQException):
    """Raised when input validation fails."""
    pass


class AuthenticationException(ProcureIQException):
    """Raised for authentication/authorization failures."""
    pass


class ExternalServiceException(ProcureIQException):
    """Raised when external services (Twilio, ERP, etc.) fail."""
    pass


class ConfigurationException(ProcureIQException):
    """Raised for configuration/environment errors."""
    pass
