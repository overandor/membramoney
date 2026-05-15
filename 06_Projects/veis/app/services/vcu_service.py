import uuid
from datetime import datetime, timedelta
from typing import Optional
from app.core.logging import get_logger
from app.models.verification import Verification
from app.models.vcu import VCU, VCUStatus

logger = get_logger(__name__)


class VCUService:
    """Service for Verified Cleanup Unit (VCU) management"""
    
    def generate_vcu(
        self,
        verification: Verification,
        amount_kg: float,
        owner: str
    ) -> VCU:
        """
        Generate a VCU for a verified cleanup
        """
        logger.info(
            "Generating VCU",
            verification_id=verification.id,
            amount_kg=amount_kg,
            owner=owner
        )
        
        # Generate unique token ID
        token_id = f"VCU-{uuid.uuid4().hex[:16].upper()}"
        
        # Calculate CO2 equivalent (roughly 1kg waste = 0.5kg CO2)
        co2_equivalent = amount_kg / 1000 * 0.5
        
        # Create VCU
        vcu = VCU(
            verification_id=verification.id,
            token_id=token_id,
            amount=co2_equivalent,
            current_owner=owner,
            original_owner=owner,
            status=VCUStatus.ACTIVE,
            expires_at=datetime.utcnow() + timedelta(days=365),  # 1 year expiry
            metadata=json.dumps({
                "verification_id": verification.id,
                "waste_type": verification.observation.waste_type,
                "location": {
                    "latitude": verification.observation.latitude,
                    "longitude": verification.observation.longitude
                },
                "removed_mass_g": verification.removed_mass_g
            })
        )
        
        logger.info(
            "VCU generated successfully",
            vcu_id=vcu.id,
            token_id=token_id
        )
        
        return vcu
    
    def transfer_vcu(
        self,
        vcu: VCU,
        new_owner: str
    ) -> VCU:
        """
        Transfer ownership of a VCU
        """
        logger.info(
            "Transferring VCU",
            vcu_id=vcu.id,
            from_owner=vcu.current_owner,
            to_owner=new_owner
        )
        
        # Update ownership
        vcu.current_owner = new_owner
        vcu.status = VCUStatus.TRANSFERRED
        vcu.transferred_at = datetime.utcnow()
        
        # Update transfer history
        history = []
        if vcu.transfer_history:
            history = json.loads(vcu.transfer_history)
        
        history.append({
            "from": vcu.original_owner,
            "to": new_owner,
            "at": vcu.transferred_at.isoformat()
        })
        
        vcu.transfer_history = json.dumps(history)
        
        logger.info(
            "VCU transferred successfully",
            vcu_id=vcu.id
        )
        
        return vcu
    
    def redeem_vcu(self, vcu: VCU) -> VCU:
        """
        Redeem a VCU (mark as used)
        """
        logger.info(
            "Redeeming VCU",
            vcu_id=vcu.id,
            owner=vcu.current_owner
        )
        
        vcu.status = VCUStatus.REDEEMED
        
        logger.info(
            "VCU redeemed successfully",
            vcu_id=vcu.id
        )
        
        return vcu
