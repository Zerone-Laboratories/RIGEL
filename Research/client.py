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
        print()
        
        while True:
            print("\nChoose an endpoint (1-4) or 'quit' to exit:")
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
            else:
                print("Invalid choice. Please enter 1-4 or 'quit'.")
        
    except Exception as e:
        print(f"Error connecting to RIGEL service: {e}")
        print("Make sure the RIGEL D-Bus server is running (python server.py)")

if __name__ == "__main__":
    test_rigel_service()
