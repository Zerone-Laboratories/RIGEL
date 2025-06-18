from pydbus import SessionBus

def test_rigel_service():
    """Test the RIGEL D-Bus service"""
    try:
        bus = SessionBus()
        service = bus.get("com.rigel.RigelService")
        
        # Test basic query
        response = service.Query("Hello RIGEL! How are you?")
        print(f"RIGEL: {response}")
        
        # Test another query
        response2 = service.Query("What is the capital of France?")
        print(f"RIGEL: {response2}")
        
    except Exception as e:
        print(f"Error connecting to RIGEL service: {e}")
        print("Make sure the RIGEL D-Bus server is running (python server.py)")

if __name__ == "__main__":
    test_rigel_service()
