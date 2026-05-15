import pytest
from app.services.verification_service import VerificationService
from app.models.observation import Observation, ObservationStatus
from app.models.verification import VerificationStatus


@pytest.fixture
def verification_service():
    """Fixture for VerificationService"""
    return VerificationService()


@pytest.fixture
def mock_observation():
    """Fixture for mock observation"""
    observation = Observation(
        id=1,
        image_url="test_image.jpg",
        latitude=40.7128,
        longitude=-74.0060,
        estimated_mass_g=1000.0,
        confidence_score=0.9,
        status=ObservationStatus.COMPLETED
    )
    return observation


@pytest.mark.asyncio
async def test_verify_cleanup(verification_service, mock_observation):
    """Test cleanup verification"""
    result = await verification_service.verify_cleanup(
        observation=mock_observation,
        followup_image_url="followup_image.jpg"
    )
    
    assert "removed_mass_g" in result
    assert "fraud_risk_score" in result
    assert "similarity_score" in result
    assert "status" in result
    assert result["removed_mass_g"] >= 0
    assert 0.0 <= result["fraud_risk_score"] <= 1.0
    assert result["status"] in [VerificationStatus.VERIFIED, VerificationStatus.REJECTED, VerificationStatus.FRAUD_DETECTED]


def test_calculate_fraud_risk(verification_service):
    """Test fraud risk calculation"""
    # High similarity (waste not removed)
    risk1 = verification_service._calculate_fraud_risk(0.8, 0.9)
    assert risk1 > 0.3
    
    # Low similarity (waste removed)
    risk2 = verification_service._calculate_fraud_risk(0.1, 0.9)
    assert risk2 < risk1
