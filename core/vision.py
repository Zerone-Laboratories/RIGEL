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
Vision module for RIGEL Engine.
Provides image analysis capabilities using vision models (GPT-4V, local LLaVA, etc.)
"""

import os
import base64
import json
import tempfile
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.logger import SysLog

# Initialize logger
syslog = SysLog(name="Vision", level="INFO", log_file="rigel.log")

# Try to import httpx for async API calls
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    syslog.warning("httpx not installed. Vision API calls will be limited.")

# Try to import PIL for image handling
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    syslog.warning("PIL not installed. Image preprocessing will be limited.")


class VisionEngine:
    """
    Vision analysis engine for RIGEL.
    Supports multiple backends: OpenAI GPT-4V, local Ollama vision models, etc.
    """
    
    def __init__(
        self,
        backend: str = "openai",
        model: str = None,
        api_key: str = None,
        api_base: str = None,
        ollama_host: str = None
    ):
        """
        Initialize the vision engine.
        
        Args:
            backend: Vision backend to use ("openai", "ollama", "groq")
            model: Model name (default: gpt-4o for openai, llava for ollama)
            api_key: API key for cloud providers
            api_base: Base URL for API (for custom endpoints)
            ollama_host: Ollama host URL (default: http://localhost:11434)
        """
        self.backend = backend.lower()
        
        # Set defaults based on backend
        if self.backend == "openai":
            self.model = model or os.getenv("VISION_MODEL", "gpt-4o")
            self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
            self.api_base = api_base or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        elif self.backend == "ollama":
            self.model = model or os.getenv("OLLAMA_VISION_MODEL", "llava")
            self.ollama_host = ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        elif self.backend == "groq":
            self.model = model or os.getenv("GROQ_VISION_MODEL", "llama-3.2-90b-vision-preview")
            self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
            self.api_base = "https://api.groq.com/openai/v1"
        else:
            raise ValueError(f"Unsupported vision backend: {backend}")
        
        self.screenshots_dir = tempfile.mkdtemp(prefix="rigel_vision_")
        syslog.info(f"VisionEngine initialized with backend={self.backend}, model={self.model}")
    
    def _load_image_as_base64(self, image_path: str) -> str:
        """Load an image file and convert to base64"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def _get_image_mime_type(self, image_path: str) -> str:
        """Detect image MIME type from file extension"""
        ext = os.path.splitext(image_path)[1].lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp"
        }
        return mime_types.get(ext, "image/png")
    
    async def analyze_image_async(
        self,
        image_source: str,
        prompt: str,
        max_tokens: int = 1024,
        detail: str = "high"
    ) -> Dict[str, Any]:
        """
        Analyze an image asynchronously with vision model.
        
        Args:
            image_source: Path to image file OR base64-encoded image data
            prompt: Analysis prompt/question about the image
            max_tokens: Maximum tokens in response
            detail: Image detail level ("low", "high", "auto")
            
        Returns:
            Analysis result dictionary
        """
        if not HTTPX_AVAILABLE:
            return {"error": "httpx not installed", "analysis": None}
        
        # Determine if source is file path or base64
        if os.path.exists(image_source):
            image_b64 = self._load_image_as_base64(image_source)
            mime_type = self._get_image_mime_type(image_source)
        else:
            # Assume it's already base64
            image_b64 = image_source
            mime_type = "image/png"
        
        try:
            if self.backend == "openai" or self.backend == "groq":
                return await self._analyze_openai_compatible(image_b64, mime_type, prompt, max_tokens, detail)
            elif self.backend == "ollama":
                return await self._analyze_ollama(image_b64, prompt, max_tokens)
            else:
                return {"error": f"Unsupported backend: {self.backend}"}
        except Exception as e:
            syslog.error(f"Vision analysis error: {str(e)}")
            return {"error": str(e), "analysis": None}
    
    async def _analyze_openai_compatible(
        self,
        image_b64: str,
        mime_type: str,
        prompt: str,
        max_tokens: int,
        detail: str
    ) -> Dict[str, Any]:
        """Analyze image using OpenAI-compatible API (GPT-4V, Groq, etc.)"""
        if not self.api_key:
            return {"error": "API key not configured", "analysis": None}
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{image_b64}",
                                        "detail": detail
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": max_tokens
                }
            )
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "analysis": result["choices"][0]["message"]["content"],
                "model": self.model,
                "backend": self.backend,
                "usage": result.get("usage", {})
            }
    
    async def _analyze_ollama(
        self,
        image_b64: str,
        prompt: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Analyze image using local Ollama vision model"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "analysis": result.get("response", ""),
                "model": self.model,
                "backend": "ollama",
                "eval_count": result.get("eval_count", 0)
            }
    
    def analyze_image(
        self,
        image_source: str,
        prompt: str,
        max_tokens: int = 1024,
        detail: str = "high"
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for image analysis.
        
        Args:
            image_source: Path to image file OR base64-encoded image data
            prompt: Analysis prompt/question about the image
            max_tokens: Maximum tokens in response
            detail: Image detail level
            
        Returns:
            Analysis result dictionary
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use thread executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.analyze_image_async(image_source, prompt, max_tokens, detail)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.analyze_image_async(image_source, prompt, max_tokens, detail)
                )
        except RuntimeError:
            return asyncio.run(
                self.analyze_image_async(image_source, prompt, max_tokens, detail)
            )
    
    def describe_image(self, image_source: str) -> str:
        """
        Get a detailed description of an image.
        
        Args:
            image_source: Path to image or base64 data
            
        Returns:
            Text description of the image
        """
        result = self.analyze_image(
            image_source,
            prompt="""Provide a detailed description of this image including:
1. Main subject and composition
2. Colors, lighting, and mood
3. Any text visible in the image
4. Notable objects or people
5. Background and environment"""
        )
        return result.get("analysis", result.get("error", "Analysis failed"))
    
    def extract_text(self, image_source: str) -> str:
        """
        Extract text (OCR) from an image using vision model.
        
        Args:
            image_source: Path to image or base64 data
            
        Returns:
            Extracted text from the image
        """
        result = self.analyze_image(
            image_source,
            prompt="""Extract ALL text visible in this image. 
Include:
- Main text content
- Labels and captions
- Any visible UI text
- Numbers and codes
Format the extracted text clearly, preserving the layout where possible."""
        )
        return result.get("analysis", result.get("error", "Text extraction failed"))
    
    def analyze_screenshot(self, image_source: str, context: str = "") -> Dict[str, Any]:
        """
        Analyze a screenshot for UI elements and actions.
        
        Args:
            image_source: Path to screenshot or base64 data
            context: Additional context about what we're looking for
            
        Returns:
            Analysis with UI elements, suggested actions, etc.
        """
        prompt = f"""Analyze this screenshot and provide:
1. Application/website identification
2. Main content visible
3. Interactive elements (buttons, links, inputs, menus)
4. Current state (logged in/out, page section, etc.)
5. Suggested next actions

{f'Additional context: {context}' if context else ''}

Format response as structured information."""
        
        result = self.analyze_image(image_source, prompt, max_tokens=2048)
        return result
    
    def find_element(self, image_source: str, element_description: str) -> Dict[str, Any]:
        """
        Find a specific element in a screenshot by description.
        
        Args:
            image_source: Path to screenshot or base64 data
            element_description: Description of element to find
            
        Returns:
            Location and selector information for the element
        """
        prompt = f"""Find the element described as: "{element_description}"

Provide:
1. Whether the element is visible (yes/no)
2. Location on screen (top/middle/bottom, left/center/right)
3. Approximate coordinates (x%, y% from top-left)
4. Suggested CSS selector or identifier
5. The element's current state (enabled, disabled, selected, etc.)
6. Any text on or near the element

Format as JSON."""
        
        result = self.analyze_image(image_source, prompt, max_tokens=1024)
        return result
    
    def compare_images(self, image1_source: str, image2_source: str) -> Dict[str, Any]:
        """
        Compare two images and describe differences.
        Note: This sends both images in sequence with context.
        
        Args:
            image1_source: First image path or base64
            image2_source: Second image path or base64
            
        Returns:
            Comparison analysis
        """
        # For comparison, we analyze first image then second with context
        result1 = self.analyze_image(
            image1_source,
            "Describe this image in detail, focusing on key elements and their positions."
        )
        
        result2 = self.analyze_image(
            image2_source,
            f"""Compare this image to the following description of another image:
{result1.get('analysis', '')}

Describe:
1. What is the same
2. What has changed
3. What is new
4. What is missing"""
        )
        
        return {
            "success": True,
            "image1_analysis": result1.get("analysis"),
            "comparison": result2.get("analysis"),
            "model": self.model
        }


# Singleton instance for easy access
_vision_engine = None

def get_vision_engine() -> VisionEngine:
    """Get or create the global vision engine instance"""
    global _vision_engine
    if _vision_engine is None:
        backend = os.getenv("VISION_BACKEND", "openai")
        _vision_engine = VisionEngine(backend=backend)
    return _vision_engine


def analyze_image(image_source: str, prompt: str) -> str:
    """Convenience function for quick image analysis"""
    engine = get_vision_engine()
    result = engine.analyze_image(image_source, prompt)
    return result.get("analysis", result.get("error", "Analysis failed"))


def describe_image(image_source: str) -> str:
    """Convenience function for image description"""
    engine = get_vision_engine()
    return engine.describe_image(image_source)


def extract_text_from_image(image_source: str) -> str:
    """Convenience function for OCR"""
    engine = get_vision_engine()
    return engine.extract_text(image_source)
