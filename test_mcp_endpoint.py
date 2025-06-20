# This file is part of RIGEL_ENGINE.
#
# RIGEL_ENGINE is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RIGEL_ENGINE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from pydbus import SessionBus
import time

def test_mcp_endpoint():
    """Test the new QueryWithTools D-Bus endpoint"""
    try:
        bus = SessionBus()
        service = bus.get("com.rigel.RigelService")
        
        print("Testing RIGEL MCP D-Bus Endpoint")
        print("=" * 40)
        test_cases = [
            "What time is it?",
            "List the files in the current directory",
            "Get system information",
            "Read the first 5 lines of the README.md file",
            "What is the current working directory and who am I?",
        ]
        
        for i, query in enumerate(test_cases, 1):
            print(f"\nTest {i}: {query}")
            print("-" * 30)
            
            try:
                response = service.QueryWithTools(query)
                print(f"Response: {response}")
            except Exception as e:
                print(f"Error: {e}")
            time.sleep(1)
        
        print("\n" + "=" * 40)
        print("MCP endpoint testing completed!")
        
    except Exception as e:
        print(f"Error connecting to RIGEL service: {e}")
        print("Make sure:")
        print("1. The RIGEL D-Bus server is running (python server.py)")
        print("2. You have selected a backend (Groq or Ollama)")
        print("3. Required dependencies are installed")

if __name__ == "__main__":
    test_mcp_endpoint()
