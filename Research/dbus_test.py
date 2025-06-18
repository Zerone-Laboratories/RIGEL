from pydbus import SessionBus
from gi.repository import GLib

loop = GLib.MainLoop()

class MyService(object):
    """
    <node>
        <interface name='com.example.MyService'>
            <method name='Hello'>
                <arg type='s' name='name' direction='in'/>
                <arg type='s' name='greeting' direction='out'/>
            </method>
        </interface>
    </node>
    """

    def Hello(self, name):
        return f"Hello, {name}!"

bus = SessionBus()
bus.publish("com.example.MyService", MyService())

print("Service running...")
loop.run()
