"""
Centralized configuration management for Procure-IQ.
All environment variables and settings are loaded and validated here.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All secrets must be stored in .env file (never commit .env to git).
    """
    
    # ═══════════════════════════════════════════
    # SERVER CONFIGURATION
    # ═══════════════════════════════════════════
    PORT: int = Field(default=8000, description="Server port")
    API_KEY: Optional[str] = Field(default=None, description="API authentication key")
    BASE_URL: str = Field(default="http://localhost:8000", description="Base URL for links")
    
    # ═══════════════════════════════════════════
    # AI MODELS (v2.0)
    # ═══════════════════════════════════════════
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API key")
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key (fallback)")
    AI_MODEL_PRIMARY: str = Field(default="gemini-1.5-pro", description="Primary AI model")
    AI_MODEL_FALLBACK: str = Field(default="gpt-4o", description="Fallback AI model")
    
    # ═══════════════════════════════════════════
    # GMAIL OAUTH2 (v2.0)
    # ═══════════════════════════════════════════
    GMAIL_CLIENT_ID: Optional[str] = Field(default=None, description="Gmail OAuth client ID")
    GMAIL_CLIENT_SECRET: Optional[str] = Field(default=None, description="Gmail OAuth client secret")
    GMAIL_REFRESH_TOKEN: Optional[str] = Field(default=None, description="Gmail OAuth refresh token")
    
    # ═══════════════════════════════════════════
    # NOTIFICATIONS
    # ═══════════════════════════════════════════
    OWNER_EMAIL: str = Field(default="akilmakil96@gmail.com", description="Owner email for alerts")
    OWNER_PHONE: Optional[str] = Field(default=None, description="Owner phone for SMS alerts")
    SUPPLIER_EMAIL: str = Field(default="richardat125@gmail.com", description="Default supplier email")
    
    # ═══════════════════════════════════════════
    # TWILIO SMS (v2.0)
    # ═══════════════════════════════════════════
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None, description="Twilio account SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None, description="Twilio auth token")
    TWILIO_FROM_NUMBER: Optional[str] = Field(default=None, description="Twilio phone number")
    
    # ═══════════════════════════════════════════
    # DATABASE
    # ═══════════════════════════════════════════
    DATABASE_URL: str = Field(default="sqlite:///./procure_iq.db", description="Database connection URL")
    
    # ═══════════════════════════════════════════
    # ERP INTEGRATION (v2.0)
    # ═══════════════════════════════════════════
    ERP_TYPE: str = Field(default="local", description="ERP type: local, sap, netsuite, custom")
    ERP_API_URL: Optional[str] = Field(default=None, description="ERP API base URL")
    ERP_API_KEY: Optional[str] = Field(default=None, description="ERP API key")
    DATABASE_NAME: Optional[str] = Field(default=None, description="Generic database name storage")
    USERNAME: Optional[str] = Field(default=None, description="Generic username storage")
    
    # ═══════════════════════════════════════════
    # VISION/OCR MODEL
    # ═══════════════════════════════════════════
    VISION_MODEL: Optional[str] = Field(default="llama3.1:8b", description="Vision/OCR model")
    
    # ═══════════════════════════════════════════
    # BUSINESS LOGIC THRESHOLDS
    # ═══════════════════════════════════════════
    STOCK_ALERT_THRESHOLD: int = Field(default=10, description="Default low stock threshold")
    INVOICE_APPROVAL_THRESHOLD: float = Field(default=500.0, description="Invoice amount requiring approval")
    APPROVAL_TOKEN_EXPIRY_HOURS: int = Field(default=48, description="Hours before approval token expires")
    CONFIDENCE_AUTO_APPROVE: float = Field(default=0.95, description="Auto-approve confidence threshold")
    CONFIDENCE_REVIEW_THRESHOLD: float = Field(default=0.75, description="Review confidence threshold")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env
    
    def get_service_status(self) -> dict:
        """
        Return configuration status for all services.
        Masks secrets for security.
        """
        return {
            "server": {
                "port": self.PORT,
                "base_url": self.BASE_URL,
                "api_auth": "[OK] Configured" if self.API_KEY else "[WARN] Not set (will auto-generate)"
            },
            "ai_models": {
                "gemini": "[OK] Configured" if self.GEMINI_API_KEY else "[X] Not configured",
                "openai_fallback": "[OK] Configured" if self.OPENAI_API_KEY else "[X] Not configured",
                "primary_model": self.AI_MODEL_PRIMARY,
                "fallback_model": self.AI_MODEL_FALLBACK
            },
            "notifications": {
                "email": {
                    "owner": self.OWNER_EMAIL,
                    "supplier": self.SUPPLIER_EMAIL,
                    "gmail_oauth": "[OK] Configured" if self.GMAIL_CLIENT_ID else "[X] Not configured"
                },
                "sms": "[OK] Configured" if self.TWILIO_ACCOUNT_SID else "[X] Not configured"
            },
            "erp": {
                "type": self.ERP_TYPE,
                "status": "[OK] Configured" if self.ERP_TYPE != "local" and self.ERP_API_URL else "Using local database"
            },
            "database": {
                "type": "SQLite" if "sqlite" in self.DATABASE_URL.lower() else "Other",
                "url": self.DATABASE_URL.split("///")[-1] if "sqlite" in self.DATABASE_URL.lower() else "***"
            }
        }
    
    def print_startup_summary(self):
        """Print a formatted startup configuration summary."""
        status = self.get_service_status()
        
        print("\n" + "=" * 60)
        print("  PROCURE-IQ v2.0 - Configuration Summary")
        print("=" * 60)
        
        print(f"\nSERVER")
        print(f"   Port: {status['server']['port']}")
        print(f"   Base URL: {status['server']['base_url']}")
        print(f"   API Auth: {status['server']['api_auth']}")
        
        print(f"\nAI MODELS")
        print(f"   Gemini: {status['ai_models']['gemini']}")
        print(f"   OpenAI: {status['ai_models']['openai_fallback']}")
        print(f"   Primary: {status['ai_models']['primary_model']}")
        
        print(f"\nNOTIFICATIONS")
        print(f"   Owner Email: {status['notifications']['email']['owner']}")
        print(f"   Gmail OAuth: {status['notifications']['email']['gmail_oauth']}")
        print(f"   SMS (Twilio): {status['notifications']['sms']}")
        
        print(f"\nDATABASE")
        print(f"   Type: {status['database']['type']}")
        print(f"   Location: {status['database']['url']}")
        
        print(f"\nERP")
        print(f"   Type: {status['erp']['type']}")
        print(f"   Status: {status['erp']['status']}")
        
        print("\n" + "=" * 60)
        
        # Warnings
        warnings = []
        if not self.GEMINI_API_KEY and not self.OPENAI_API_KEY:
            warnings.append("WARNING: No AI API keys configured - v2.0 features will be limited")
        if not self.GMAIL_CLIENT_ID:
            warnings.append("WARNING: Gmail OAuth not configured - email features disabled")
        if not self.TWILIO_ACCOUNT_SID:
            warnings.append("WARNING: Twilio not configured - SMS alerts disabled")
        
        if warnings:
            print("\nWARNINGS:")
            for warning in warnings:
                print(f"   {warning}")
            print()


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
