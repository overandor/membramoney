"""
Image Processor - Isolated module for image classification
Can be swapped between mock and real implementation
"""

from typing import Dict, Any, Tuple
from PIL import Image


class ImageProcessor:
    """Image classification processor - mock or real"""
    
    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        
    def process(self, image_path: str) -> Dict[str, Any]:
        """
        Process image and return classification results
        
        Returns:
            {
                "classification": str,  # "cigarette_butts", "trash", "none"
                "estimated_count": int,
                "confidence": float,  # 0.0 to 1.0
                "image_width": int,
                "image_height": int
            }
        """
        # Load image dimensions
        with Image.open(image_path) as img:
            width, height = img.size
        
        if self.use_mock:
            return self._mock_process(width, height)
        else:
            return self._real_process(image_path, width, height)
    
    def _mock_process(self, width: int, height: int) -> Dict[str, Any]:
        """Mock classification for testing - REPLACE WITH REAL MODEL"""
        # TODO: Replace with actual YOLO/OpenCV model
        # This is a deterministic mock for testing only
        
        # Use image dimensions to generate consistent mock results
        # (so same image always gives same result)
        mock_count = (width + height) % 20 + 1  # 1-20
        mock_confidence = 0.7 + ((width * height) % 15) / 100  # 0.70-0.84
        
        return {
            "classification": "cigarette_butts",
            "estimated_count": mock_count,
            "confidence": round(mock_confidence, 2),
            "image_width": width,
            "image_height": height,
            "processor": "MOCK"  # Flag to indicate mock usage
        }
    
    def _real_process(self, image_path: str, width: int, height: int) -> Dict[str, Any]:
        """
        Real image classification - TO BE IMPLEMENTED
        
        Options for implementation:
        1. YOLOv8 for object detection
        2. OpenCV + custom classifier
        3. Hugging Face transformer model
        4. Ollama with vision model (if available)
        """
        # TODO: Implement real image classification
        # For now, fall back to mock
        return self._mock_process(width, height)


def create_processor(use_mock: bool = True) -> ImageProcessor:
    """Factory function to create image processor"""
    return ImageProcessor(use_mock=use_mock)
