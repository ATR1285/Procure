"""
AI Output Validators

Validates AI model outputs for format, confidence, and safety.
Author: Part 3 Team Member (Visrutha)
"""

import re
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class AIOutputValidator:
    """
    Validates AI model outputs to ensure they meet expected format and safety requirements.
    """
    
    def __init__(self, min_confidence: float = 0.0, max_confidence: float = 100.0):
        """
        Initialize validator with confidence thresholds.
        
        Args:
            min_confidence: Minimum acceptable confidence score
            max_confidence: Maximum acceptable confidence score
        """
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence
    
    def validate_vendor_match_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate vendor matching AI output.
        
        Expected format:
        {
            "vendor_id": int,
            "confidence": float (0-100),
            "reasoning": str,
            "method": str
        }
        
        Args:
            output: AI model output dictionary
            
        Returns:
            dict: Validation result with 'valid' boolean and 'errors' list
        """
        errors = []
        warnings = []
        
        # Check required fields
        required_fields = ["vendor_id", "confidence", "reasoning"]
        for field in required_fields:
            if field not in output:
                errors.append(f"Missing required field: {field}")
        
        # Validate vendor_id
        if "vendor_id" in output:
            if not isinstance(output["vendor_id"], int):
                errors.append(f"vendor_id must be integer, got {type(output['vendor_id'])}")
            elif output["vendor_id"] <= 0:
                errors.append(f"vendor_id must be positive, got {output['vendor_id']}")
        
        # Validate confidence score
        if "confidence" in output:
            confidence = output["confidence"]
            if not isinstance(confidence, (int, float)):
                errors.append(f"confidence must be numeric, got {type(confidence)}")
            elif not (self.min_confidence <= confidence <= self.max_confidence):
                errors.append(f"confidence {confidence} outside valid range [{self.min_confidence}, {self.max_confidence}]")
            
            # Warnings for edge cases
            if confidence == 100.0:
                warnings.append("Perfect confidence (100%) is unusual - verify AI output")
            elif confidence < 50.0:
                warnings.append("Low confidence - consider human review")
        
        # Validate reasoning
        if "reasoning" in output:
            reasoning = output["reasoning"]
            if not isinstance(reasoning, str):
                errors.append(f"reasoning must be string, got {type(reasoning)}")
            elif len(reasoning) < 10:
                warnings.append("Reasoning is very short - may lack detail")
            elif len(reasoning) > 1000:
                warnings.append("Reasoning is very long - may be verbose")
            
            # Check for hallucination indicators
            hallucination_indicators = [
                "I don't know",
                "I'm not sure",
                "Maybe",
                "Possibly",
                "unclear"
            ]
            if any(indicator.lower() in reasoning.lower() for indicator in hallucination_indicators):
                warnings.append("Reasoning contains uncertainty indicators - verify output")
        
        is_valid = len(errors) == 0
        
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "sanitized_output": self._sanitize_output(output) if is_valid else None
        }
    
    def _sanitize_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize AI output by removing potentially harmful content.
        
        Args:
            output: Raw AI output
            
        Returns:
            dict: Sanitized output
        """
        sanitized = output.copy()
        
        # Remove any potential SQL injection attempts
        if "reasoning" in sanitized:
            reasoning = sanitized["reasoning"]
            # Remove SQL keywords (basic protection)
            sql_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "SELECT"]
            for keyword in sql_keywords:
                if keyword in reasoning.upper():
                    logger.warning(f"Detected SQL keyword '{keyword}' in AI reasoning")
                    reasoning = reasoning.replace(keyword, "[FILTERED]")
                    reasoning = reasoning.replace(keyword.lower(), "[FILTERED]")
            sanitized["reasoning"] = reasoning
        
        return sanitized
    
    def validate_confidence_threshold(self, confidence: float, threshold_type: str = "auto_approve") -> bool:
        """
        Check if confidence meets threshold for specific action.
        
        Args:
            confidence: Confidence score (0-100)
            threshold_type: Type of threshold ('auto_approve', 'review', 'escalate')
            
        Returns:
            bool: True if confidence meets threshold
        """
        thresholds = {
            "auto_approve": 95.0,
            "review": 75.0,
            "escalate": 0.0
        }
        
        threshold = thresholds.get(threshold_type, 75.0)
        return confidence >= threshold


class OutputSchemaValidator:
    """
    Validates that AI outputs conform to expected JSON schemas.
    
    TODO: Implement JSON schema validation for different AI tasks
    """
    
    def __init__(self, schema: Dict[str, Any]):
        """
        Initialize with expected schema.
        
        Args:
            schema: JSON schema dictionary
        """
        self.schema = schema
    
    def validate(self, output: Dict[str, Any]) -> bool:
        """
        Validate output against schema.
        
        TODO: Implement using jsonschema library
        
        Args:
            output: AI output to validate
            
        Returns:
            bool: True if valid
        """
        # Placeholder - implement full schema validation
        return True


# TODO for Part 3 Team Member (Visrutha):
# - Add more sophisticated hallucination detection
# - Implement structured output validation using Pydantic
# - Add tests for all validators
# - Integrate with ai_client.py
# - Add logging and metrics
