"""
Simple test script to verify Morning Agent backend functionality
Run this after setting up .env to test core services
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.groq_llm import get_groq_llm
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.config import settings

async def test_groq():
    """Test Groq LLM service"""
    print("=" * 60)
    print("Testing Groq LLM Service")
    print("=" * 60)
    
    try:
        groq = get_groq_llm()
        response = await groq.process(
            text="Hello, I need to schedule a dentist appointment",
            instructions="You are a dental office scheduler",
            conversation_history=[]
        )
        print(f"✅ Groq LLM working")
        print(f"Response: {response[:100]}...")
        return True
    except Exception as e:
        print(f"❌ Groq LLM error: {e}")
        print(f"   Make sure GROQ_API_KEY is set in .env")
        return False

async def test_stt():
    """Test STT service"""
    print("\n" + "=" * 60)
    print("Testing STT Service")
    print("=" * 60)
    
    try:
        stt = STTService()
        # STT is a stub, so it returns a placeholder
        result = await stt.transcribe(b"fake_audio_data")
        print(f"✅ STT service initialized")
        print(f"Result: {result}")
        print(f"   (STT is a stub - integrate with Whisper/Google/Deepgram)")
        return True
    except Exception as e:
        print(f"❌ STT error: {e}")
        return False

async def test_tts():
    """Test TTS service"""
    print("\n" + "=" * 60)
    print("Testing TTS Service")
    print("=" * 60)
    
    try:
        tts = TTSService()
        # TTS is a stub, so it returns None
        result = await tts.synthesize("Hello, this is a test")
        print(f"✅ TTS service initialized")
        print(f"Result: {result}")
        print(f"   (TTS is a stub - integrate with ElevenLabs/Google/AWS)")
        return True
    except Exception as e:
        print(f"❌ TTS error: {e}")
        return False

async def test_config():
    """Test configuration"""
    print("\n" + "=" * 60)
    print("Testing Configuration")
    print("=" * 60)
    
    required_keys = [
        "twilio_account_sid",
        "twilio_auth_token",
        "twilio_from_number",
        "groq_api_key",
    ]
    
    missing = []
    for key in required_keys:
        value = getattr(settings, key, "")
        if not value:
            missing.append(key)
        else:
            # Mask sensitive values
            masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            print(f"✅ {key}: {masked}")
    
    if missing:
        print(f"\n❌ Missing environment variables: {', '.join(missing)}")
        print("   Add these to your .env file")
        return False
    
    return True

async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Morning Agent Backend Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test configuration
    results.append(("Configuration", await test_config()))
    
    # Test Groq (requires API key)
    if settings.groq_api_key:
        results.append(("Groq LLM", await test_groq()))
    else:
        print("\n⚠️  Skipping Groq test (no API key)")
        results.append(("Groq LLM", None))
    
    # Test STT and TTS (stubs)
    results.append(("STT Service", await test_stt()))
    results.append(("TTS Service", await test_tts()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    
    for name, result in results:
        if result is True:
            print(f"✅ {name}")
        elif result is False:
            print(f"❌ {name}")
        else:
            print(f"⚠️  {name} (skipped)")
    
    print(f"\nPassed: {passed}, Failed: {failed}, Skipped: {skipped}")
    
    if failed > 0:
        print("\n⚠️  Some tests failed. Fix the issues above.")
        return 1
    else:
        print("\n✅ All tests passed! Backend is ready.")
        return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
