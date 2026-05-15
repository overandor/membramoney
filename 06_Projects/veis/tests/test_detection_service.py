import pytest
from app.services.detection_service import DetectionService


@pytest.fixture
def detection_service():
    """Fixture for DetectionService"""
    return DetectionService()


@pytest.mark.asyncio
async def test_detect_waste(detection_service):
    """Test waste detection"""
    result = await detection_service.detect_waste("test_image.jpg")
    
    assert "waste_type" in result
    assert "confidence_score" in result
    assert "estimated_mass_g" in result
    assert 0.0 <= result["confidence_score"] <= 1.0
    assert result["estimated_mass_g"] > 0


@pytest.mark.asyncio
async def test_batch_detect(detection_service):
    """Test batch waste detection"""
    image_urls = ["test1.jpg", "test2.jpg", "test3.jpg"]
    results = await detection_service.batch_detect(image_urls)
    
    assert len(results) == 3
    for result in results:
        assert "waste_type" in result
        assert "confidence_score" in result
