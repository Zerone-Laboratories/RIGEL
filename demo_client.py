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


from pydbus import SessionBus

def test_rigel_service():
    """Test the RIGEL D-Bus service"""
    try:
        bus = SessionBus()
        service = bus.get("com.rigel.RigelService")
        
        print("RIGEL D-Bus Client")
        print("Available endpoints:")
        print("1. Query - Basic inference")
        print("2. QueryWithMemory - Inference with conversation memory")
        print("3. QueryThink - Advanced thinking")
        print("4. QueryWithTools - Inference with MCP tools")
        print("5. SynthesizeText - Text-to-speech synthesis")
        print("6. RecognizeAudio - Audio-to-text recognition")
        print()
        
        while True:
            print("\nChoose an endpoint (1-6) or 'quit' to exit:")
            choice = input("> ").strip()
            
            if choice.lower() == 'quit':
                break
            elif choice == "1":
                query = input("Enter Query: ")
                response = service.Query(query)
                print(f"RIGEL: {response}")
            elif choice == "2":
                query = input("Enter Query: ")
                thread_id = input("Enter Thread ID (or press enter for 'zeronebrain'): ").strip() or "zeronebrain"
                response = service.QueryWithMemory(query, thread_id)
                print(f"RIGEL: {response}")
            elif choice == "3":
                query = input("Enter Query for Thinking: ")
                response = service.QueryThink(query)
                print(f"RIGEL Think: {response}")
            elif choice == "4":
                query = input("Enter Query with Tools: ")
                response = service.QueryWithTools(query)
                print(f"RIGEL Tools: {response}")
            elif choice == "5":
                text = input("Enter text to synthesize: ")
                mode = input("Enter mode (chunk/linear, default=chunk): ").strip() or "chunk"
                response = service.SynthesizeText(text, mode)
                print(f"Synthesis: {response}")
            elif choice == "6":
                audio_path = input("Enter path to audio file: ")
                model = input("Enter model (tiny/base/small/medium/large, default=tiny): ").strip() or "tiny"
                response = service.RecognizeAudio(audio_path, model)
                print(f"Transcription: {response}")
            else:
                print("Invalid choice. Please enter 1-6 or 'quit'.")
        
    except Exception as e:
        print(f"Error connecting to RIGEL service: {e}")
        print("Make sure the RIGEL D-Bus server is running (python server.py)")

if __name__ == "__main__":
    test_rigel_service()
