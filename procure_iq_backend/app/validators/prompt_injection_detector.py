"""
Prompt Injection Detection

Detects and prevents prompt injection attacks in user inputs.
Author: Part 3 Team Member (Visrutha)
"""

import re
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class PromptInjectionDetector:
    """
    Detects potential prompt injection attempts in user-provided text.
    """
    
    # Common prompt injection patterns
    INJECTION_PATTERNS = [
        # Direct command attempts
        r"ignore\s+(previous|all|above)\s+(instructions|prompts|commands)",
        r"disregard\s+(previous|all|above)",
        r"forget\s+(everything|all|previous)",
        
        # Role manipulation
        r"you\s+are\s+(now|a)\s+(developer|admin|system|root)",
        r"act\s+as\s+(if|a)\s+",
        r"pretend\s+(to\s+be|you\s+are)",
        
        # System prompt extraction
        r"show\s+(me\s+)?(your|the)\s+(prompt|instructions|system\s+message)",
        r"what\s+(is|are)\s+your\s+(instructions|rules|prompt)",
        r"repeat\s+(your|the)\s+(instructions|prompt)",
        
        # Jailbreak attempts
        r"DAN\s+mode",
        r"developer\s+mode",
        r"unrestricted\s+mode",
        
        # Encoding tricks
        r"base64",
        r"rot13",
        r"\\x[0-9a-fA-F]{2}",  # Hex encoding
        
        # Delimiter manipulation
        r"```|~~~|###",
        r"<\|.*?\|>",
        
        # SQL/Code injection
        r"(SELECT|INSERT|UPDATE|DELETE|DROP)\s+",
        r"<script",
        r"javascript:",
        
        # System commands
        r"(sudo|rm\s+-rf|chmod|exec)",
    ]
    
    def __init__(self, sensitivity: str = "medium"):
        """
        Initialize detector with sensitivity level.
        
        Args:
            sensitivity: Detection sensitivity ('low', 'medium', 'high')
        """
        self.sensitivity = sensitivity
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.INJECTION_PATTERNS
        ]
    
    def detect(self, text: str) -> Dict[str, any]:
        """
        Detect potential prompt injection attempts.
        
        Args:
            text: User-provided text to check
            
        Returns:
            dict: Detection results with 'is_safe', 'detected_patterns', 'risk_score'
        """
        if not text or not isinstance(text, str):
            return {
                "is_safe": True,
                "detected_patterns": [],
                "risk_score": 0.0,
                "recommendation": "No text to analyze"
            }
        
        detected_patterns = []
        risk_score = 0.0
        
        # Check each pattern
        for i, pattern in enumerate(self.compiled_patterns):
            matches = pattern.findall(text)
            if matches:
                pattern_name = self.INJECTION_PATTERNS[i]
                detected_patterns.append({
                    "pattern": pattern_name,
                    "matches": matches[:3],  # Limit to first 3 matches
                    "severity": self._get_pattern_severity(pattern_name)
                })
                
                # Increase risk score based on severity
                severity = self._get_pattern_severity(pattern_name)
                if severity == "critical":
                    risk_score += 30.0
                elif severity == "high":
                    risk_score += 20.0
                elif severity == "medium":
                    risk_score += 10.0
                else:
                    risk_score += 5.0
        
        # Cap risk score at 100
        risk_score = min(risk_score, 100.0)
        
        # Determine if safe based on sensitivity and risk score
        safety_thresholds = {
            "low": 75.0,
            "medium": 50.0,
            "high": 25.0
        }
        threshold = safety_thresholds.get(self.sensitivity, 50.0)
        is_safe = risk_score < threshold
        
        # Log detection
        if not is_safe:
            logger.warning(
                f"Prompt injection detected! Risk score: {risk_score:.1f}, "
                f"Patterns: {len(detected_patterns)}"
            )
        
        recommendation = self._get_recommendation(risk_score, is_safe)
        
        return {
            "is_safe": is_safe,
            "detected_patterns": detected_patterns,
            "risk_score": risk_score,
            "recommendation": recommendation
        }
    
    def _get_pattern_severity(self, pattern: str) -> str:
        """
        Get severity level for a pattern.
        
        Args:
            pattern: Regex pattern string
            
        Returns:
            str: Severity level ('low', 'medium', 'high', 'critical')
        """
        # Critical patterns
        critical_keywords = ["ignore", "disregard", "forget", "system", "admin"]
        if any(keyword in pattern.lower() for keyword in critical_keywords):
            return "critical"
        
        # High severity patterns
        high_keywords = ["show", "repeat", "mode", "developer"]
        if any(keyword in pattern.lower() for keyword in high_keywords):
            return "high"
        
        # Medium severity patterns
        medium_keywords = ["encoding", "delimiter", "base64"]
        if any(keyword in pattern.lower() for keyword in medium_keywords):
            return "medium"
        
        return "low"
    
    def _get_recommendation(self, risk_score: float, is_safe: bool) -> str:
        """
        Get recommendation based on risk score.
        
        Args:
            risk_score: Calculated risk score
            is_safe: Whether input is safe
            
        Returns:
            str: Recommendation message
        """
        if risk_score == 0.0:
            return "✅ No injection patterns detected - safe to process"
        elif is_safe:
            return f"⚠️ Low risk ({risk_score:.1f}%) - proceed with caution"
        elif risk_score < 75.0:
            return f"🚨 Moderate risk ({risk_score:.1f}%) - sanitize input before processing"
        else:
            return f"❌ High risk ({risk_score:.1f}%) - reject input or escalate for review"
    
    def sanitize(self, text: str) -> str:
        """
        Sanitize potentially malicious input (basic implementation).
        
        Args:
            text: Input text
            
        Returns:
            str: Sanitized text
        """
        detection_result = self.detect(text)
        
        if detection_result["is_safe"]:
            return text
        
        # Remove detected patterns (basic sanitization)
        sanitized = text
        for pattern_info in detection_result["detected_patterns"]:
            for match in pattern_info["matches"]:
                sanitized = sanitized.replace(match, "[FILTERED]")
        
        logger.info(f"Sanitized input with risk score {detection_result['risk_score']:.1f}")
        
        return sanitized


# TODO for Part 3 Team Member (Visrutha):
# - Add more sophisticated detection algorithms
# - Implement machine learning-based detection
# - Add context-aware detection
# - Create comprehensive test suite
# - Add metrics and monitoring
# - Integrate with ai_client.py to protect all LLM calls
