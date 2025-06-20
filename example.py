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
RIGEL Engine v4.0 - Example Usage
This script demonstrates the key features of RIGEL including:
- Basic inference with Ollama and Groq
- Memory functionality
- RAG capabilities
"""

from core.rigel import RigelOllama, RigelGroq
from core.rdb import DBConn
import os

def demo_basic_inference():
    """Demonstrate basic inference capabilities"""
    print("=== Basic Inference Demo ===")
    
    # Initialize RIGEL with Ollama
    rigel = RigelOllama(model_name="llama3.2")
    
    messages = [
        ("system", "You are RIGEL, a helpful assistant"),
        ("human", "Explain what you are in one sentence"),
    ]
    
    response = rigel.inference(messages=messages)
    print(f"RIGEL: {response.content}")
    print()

def demo_memory_functionality():
    """Demonstrate memory functionality"""
    print("=== Memory Functionality Demo ===")
    
    rigel = RigelOllama(model_name="llama3.2")
    
    # First conversation
    print("Setting context...")
    messages1 = [("human", "My favorite color is blue. Please remember this!")]
    response1 = rigel.inference_with_memory(messages=messages1, thread_id="demo")
    print(f"RIGEL: {response1.content}")
    
    # Second conversation - should remember
    print("\nTesting memory...")
    messages2 = [("human", "What is my favorite color?")]
    response2 = rigel.inference_with_memory(messages=messages2, thread_id="demo")
    print(f"RIGEL: {response2.content}")
    
    # Show conversation history
    history = rigel.get_conversation_history(thread_id="demo")
    print(f"\nConversation history contains {len(history)} messages")
    
    # Clear memory
    rigel.clear_memory(thread_id="demo")
    print("Memory cleared!")
    print()

def demo_rag_functionality():
    """Demonstrate RAG functionality"""
    print("=== RAG Functionality Demo ===")
    
    try:
        # Initialize database
        db = DBConn()
        
        # Create a sample text file for demonstration
        sample_text = """
        RIGEL is an advanced AI assistant developed by Zerone Laboratories.
        It supports multiple backends including Ollama for local inference
        and Groq for cloud-based inference. The system is designed with
        extensibility in mind and includes features like memory management,
        RAG capabilities, and D-Bus integration for inter-process communication.
        """
        
        with open("sample_data.txt", "w") as f:
            f.write(sample_text)
        
        # Load data into RAG database
        db.load_data_from_txt_path("sample_data.txt")
        print("Sample data loaded into RAG database")
        
        # Perform similarity search
        query = "What backends does RIGEL support?"
        results = db.run_similar_serch(query)
        print(f"Query: {query}")
        print(f"RAG Results: {results[:200]}...")
        
        # Clean up
        os.remove("sample_data.txt")
        
    except Exception as e:
        print(f"RAG demo failed: {e}")
        print("This might be due to missing ChromaDB dependencies")
    
    print()

def main():
    """Run all demonstrations"""
    print("RIGEL Engine v4.0 - Feature Demonstration")
    print("=" * 50)
    
    try:
        demo_basic_inference()
        demo_memory_functionality()
        demo_rag_functionality()
        
        print("=== D-Bus Server Demo ===")
        print("To test D-Bus functionality:")
        print("1. Run: python server.py")
        print("2. In another terminal, run: python Research/client.py")
        print()
        
        print("Demo completed successfully!")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo failed: {e}")
        print("Make sure all dependencies are installed and Ollama is running")

if __name__ == "__main__":
    main()
