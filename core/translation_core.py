from googletrans import Translator as GoogleTranslator

class Translator:
    def __init__(self):
        self.translator = GoogleTranslator()
        print("Translator initialized.")

    def translate_to_italian(self, text: str) -> str:
        if not text.strip():
            return "" 

        try:
            translation = self.translator.translate(text, dest='it', src='en')
            print(f"Translation: {translation.text}")
            return translation.text
        except Exception as e:
            print(f"Error in translation: {e}")
            return f"Translation failed due as an error occurred: {text}"

    def translate_text(self, text: str, target_language: str = 'it', source_language: str = 'auto') -> str:
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
            translation = self.translator.translate(text, dest=target_language, src=source_language)
            print(f"Translation ({source_language} -> {target_language}): {translation.text}")
            return translation.text
        except Exception as e:
            print(f"Error in translation: {e}")
            return f"Translation failed due to an error: {text}"