from googletrans import Translator as GoogleTranslator
import asyncio

class Translator:
    def __init__(self):
        self.translator = GoogleTranslator()
        print("Translator initialized.")

    async def translate_to_italian(self, text: str) -> str:
        if not text.strip():
            return "" 

        try:
            translation = await self.translator.translate(text, dest='it', src='en')
            print(f"Translation: {translation.text}")
            return translation.text
        except Exception as e:
            print(f"Error in translation: {e}")
            return f"Translation failed due as an error occurred: {text}"

    async def translate_text(self, text: str, target_language: str = 'it', source_language: str = 'auto') -> str:
        """
        Translate text from source language to target language
        
        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'it', 'es', 'fr', 'de')
            source_language: Source language code ('auto' for auto-detection)
        
        Returns:
            Translated text
        """
        if not text.strip():
            return ""

        try:
            translation = await self.translator.translate(text, dest=target_language, src=source_language)
            print(f"Translation ({source_language} -> {target_language}): {translation.text}")
            return translation.text
        except Exception as e:
            print(f"Error in translation: {e}")
            return f"Translation failed due to an error: {text}"
        

async def main():
    translator = Translator()
    test_text = "Hello, how are you today?"
    result = await translator.translate_to_italian(test_text)
    print(f"Original: {test_text}")
    print(f"Italian: {result}")
    
    # Test general translation method
    test_text2 = "Good morning, welcome to our service!"
    result2 = await translator.translate_text(test_text2, target_language='es', source_language='en')
    print(f"\nOriginal: {test_text2}")
    print(f"Spanish: {result2}")
    
    # Test with auto language detection
    result3 = await translator.translate_text("Bonjour le monde", target_language='en', source_language='auto')
    print(f"\nAuto-detected French: Bonjour le monde")
    print(f"English: {result3}")

if __name__ == "__main__":
    asyncio.run(main())
