#!/usr/bin/env python3
# This file is part of RIGEL Engine.
#
# RIGEL Engine is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RIGEL Engine is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
RIGEL Voice Features Test Script

This script demonstrates the voice synthesis and recognition capabilities
of RIGEL Engine through both direct Python usage and D-Bus interface.
"""

import os
import sys
from pathlib import Path

def test_direct_voice_import():
    """Test direct import of voice modules"""
    print("=== Testing Direct Voice Module Imports ===")
    
    try:
        from core.synth_n_recog import Synthesizer, Recognizer
        print("✓ Voice modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import voice modules: {e}")
        return False

def test_synthesizer():
    """Test voice synthesis functionality"""
    print("\n=== Testing Voice Synthesis ===")
    
    try:
        from core.synth_n_recog import Synthesizer
        
        # Test chunk mode
        print("Testing chunk mode synthesis...")
        synthesizer = Synthesizer(mode="chunk")
        print("✓ Synthesizer initialized in chunk mode")
        
        # Test linear mode
        print("Testing linear mode synthesis...")
        synthesizer.mode = "linear"
        print("✓ Synthesizer mode changed to linear")
        
        return True
    except Exception as e:
        print(f"✗ Synthesizer test failed: {e}")
        return False

def test_recognizer():
    """Test voice recognition functionality"""
    print("\n=== Testing Voice Recognition ===")
    
    try:
        from core.synth_n_recog import Recognizer
        
        # Test different models
        models = ["tiny", "base"]
        for model in models:
            print(f"Testing {model} model...")
            recognizer = Recognizer(model=model)
            print(f"✓ Recognizer initialized with {model} model")
        
        return True
    except Exception as e:
        print(f"✗ Recognizer test failed: {e}")
        return False

def test_dbus_voice_interface():
    """Test voice features through D-Bus interface"""
    print("\n=== Testing D-Bus Voice Interface ===")
    
    try:
        from pydbus import SessionBus
        
        bus = SessionBus()
        service = bus.get("com.rigel.RigelService")
        
        # Test license info (quick connectivity test)
        license_info = service.GetLicenseInfo()
        print("✓ D-Bus service connection successful")
        
        # Note: Actual voice tests require audio files and system audio
        print("✓ Voice endpoints available through D-Bus:")
        print("  - SynthesizeText(text, mode)")
        print("  - RecognizeAudio(audio_file_path, model)")
        
        return True
    except Exception as e:
        print(f"✗ D-Bus voice interface test failed: {e}")
        print("  Make sure RIGEL D-Bus server is running: python server.py")
        return False

def test_dependencies():
    """Test required dependencies for voice features"""
    print("\n=== Testing Voice Dependencies ===")
    
    dependencies = {
        "whisper": "OpenAI Whisper for speech recognition",
        "torch": "PyTorch for Whisper models",
        "subprocess": "System command execution",
        "threading": "Multi-threaded audio processing",
        "queue": "Audio processing queues"
    }
    
    all_passed = True
    for dep, description in dependencies.items():
        try:
            __import__(dep)
            print(f"✓ {dep}: {description}")
        except ImportError:
            print(f"✗ {dep}: {description} - NOT AVAILABLE")
            all_passed = False
    
    return all_passed

def main():
    """Run all voice feature tests"""
    print("RIGEL Voice Features Test Suite")
    print("=" * 50)
    
    tests = [
        test_dependencies,
        test_direct_voice_import,
        test_synthesizer,
        test_recognizer,
        test_dbus_voice_interface
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print("\n" + "=" * 50)
    print("Test Results Summary:")
    print(f"Passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("🎉 All voice feature tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
