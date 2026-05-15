import json
import random
from typing import Dict, Optional
from app.core.logging import get_logger
from app.models.observation import Observation
from app.models.verification import Verification, VerificationStatus

logger = get_logger(__name__)


class VerificationService:
    """Service for cleanup verification"""
    
    async def verify_cleanup(
        self,
        observation: Observation,
        followup_image_url: str
    ) -> Dict:
        """
        Verify cleanup by comparing baseline and follow-up images
        """
        logger.info(
            "Starting cleanup verification",
            observation_id=observation.id,
            followup_image_url=followup_image_url
        )
        
        # Simulate image comparison
        similarity_score = random.uniform(0.0, 0.3)  # Lower is better (less waste)
        
        # Calculate removed mass (baseline - remaining)
        baseline_mass = observation.estimated_mass_g or 0
        remaining_mass = baseline_mass * similarity_score
        removed_mass = baseline_mass - remaining_mass
        
        # Calculate fraud risk
        fraud_risk_score = self._calculate_fraud_risk(
            similarity_score,
            observation.confidence_score
        )
        
        # Determine verification status
        if fraud_risk_score > 0.7:
            status = VerificationStatus.FRAUD_DETECTED
        elif removed_mass > (baseline_mass * 0.8):
            status = VerificationStatus.VERIFIED
        else:
            status = VerificationStatus.REJECTED
        
        verification_details = {
            "baseline_mass_g": baseline_mass,
            "remaining_mass_g": remaining_mass,
            "removed_mass_g": removed_mass,
            "similarity_score": similarity_score,
            "fraud_risk_score": fraud_risk_score,
            "verification_method": "image_similarity",
            "confidence": 1.0 - fraud_risk_score
        }
        
        logger.info(
            "Verification completed",
            observation_id=observation.id,
            status=status.value,
            verification_details=verification_details
        )
        
        return {
            "removed_mass_g": removed_mass,
            "fraud_risk_score": fraud_risk_score,
            "similarity_score": similarity_score,
            "status": status,
            "verification_details": verification_details
        }
    
    def _calculate_fraud_risk(
        self,
        similarity_score: float,
        baseline_confidence: Optional[float]
    ) -> float:
        """
        Calculate fraud risk score based on various factors
        """
        risk_score = 0.0
        
        # High similarity (waste not removed) increases fraud risk
        if similarity_score > 0.5:
            risk_score += 0.3
        
        # Low baseline confidence increases fraud risk
        if baseline_confidence and baseline_confidence < 0.5:
            risk_score += 0.2
        
        # Add some randomness for simulation
        risk_score += random.uniform(0.0, 0.1)
        
        return min(risk_score, 1.0)
