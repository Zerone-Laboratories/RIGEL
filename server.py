from pydbus import SessionBus
from gi.repository import GLib
from core.rigel import RigelOllama, RigelGroq

global rigel, system_prompt
rigel = None
system_prompt = """
You are RIGEL, a helpful assistant developed by Zerone Laboratories.
"""

class RigelServer(object):
    """
    <node>
        <interface name='com.rigel.RigelService'>
            <method name='Query'>
                <arg type='s' name='query' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
        </interface>
    </node>
    """

    def Query(self, query):
        global system_prompt, rigel
        messages = [
            (
                "system",
                f"{system_prompt}"
            ),
            (
                "human", f"{query}"
            )
        ]
        response = rigel.inference(messages=messages)
        print(response)
        return response.content
    
    """
    <node>
        <interface name='com.rigel.RigelService'>
            <method name='Query_with_memory'>
                <arg type='s' name='query' direction='in'/>
                <arg type='s' name='id' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
        </interface>
    </node>
    """

    def QueryWithMemory(self, query, id):
        global system_prompt, rigel
        messages = [
            (
                "system",
                f"{system_prompt}"
            ),
            (
                "human", f"{query}"
            )
        ]
        rigel.inference_with_memory(messages=messages, thread_id=id)
    # """
    # <node>
    #     <interface name='com.rigel.RigelService'>
    #         <method name='Query_with_memory'>
    #             <arg type='s' name='query' direction='in'/>
    #             <arg type='s' name='query' direction='in'/>
    #             <arg type='s' name='response' direction='out'/>
    #         </method>
    #     </interface>
    # </node>
    # """

    # def Query_with_memory(self, query):
    #     global system_prompt, rigel
    #     messages = [
    #         (
    #             "system",
    #             f"{system_prompt}"
    #         ),
    #         (
    #             "human", f"{query}"
    #         )
    #     ]
    #     response = rigel.inference(messages=messages)
    #     return response.content


if __name__ == "__main__":
    print("RIGEL Experimental DBUS Interface")
    print("Select Required Backend :")
    backend_choice = int(input("Select '1' for GROQ and '2' for OLLAMA "))
    
    if backend_choice == 1:
        rigel = RigelGroq()
        print("RIGEL initialized with GROQ backend")
    else:
        rigel = RigelOllama()
        print("RIGEL initialized with OLLAMA backend")

    bus = SessionBus()
    bus.publish("com.rigel.RigelService", RigelServer())
    
    print("RIGEL D-Bus service is running...")
    print("Service name: com.rigel.RigelService")
    print("Interface: com.rigel.RigelService")
    print("Method: Query")
    print("Press Ctrl+C to stop")

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nStopping RIGEL D-Bus service...")
        loop.quit()