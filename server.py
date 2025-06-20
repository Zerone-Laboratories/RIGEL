# This file is part of RIGEL Engine.
#
# Copyright (C) 2025 Zerone Laboratories
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
from gi.repository import GLib
from core.rigel import RigelOllama, RigelGroq
from core.logger import SysLog
import asyncio
import concurrent.futures
# Initialize logging
syslog = SysLog(name="RigelDBusServer", level="INFO", log_file="server.log")

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
            <method name='QueryWithMemory'>
                <arg type='s' name='query' direction='in'/>
                <arg type='s' name='id' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
            <method name='QueryThink'>
                <arg type='s' name='query' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
            <method name='QueryWithTools'>
                <arg type='s' name='query' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
            <method name='GetLicenseInfo'>
                <arg type='s' name='license_info' direction='out'/>
            </method>
        </interface>
    </node>
    """

    def GetLicenseInfo(self):
        """Return license information for AGPL compliance"""
        import json
        license_info = {
            "name": "RIGEL Engine",
            "version": "4.0.X",
            "license": "GNU Affero General Public License v3.0",
            "source": "https://github.com/Zerone-Laboratories/RIGEL",
            "copyright": "Copyright (C) 2025 Zerone Laboratories",
            "agpl_notice": "This program is free software under AGPL-3.0. If you run a modified version as a network service, you must provide source code to users."
        }
        return json.dumps(license_info, indent=2)

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
        # print(response)
        return response.content

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
        response = rigel.inference_with_memory(messages=messages, thread_id=id)
        # print(response)
        return response.content
    
    def QueryThink(self, query):
        global rigel
        response = rigel.inference(messages=query)
        return response
    
    def QueryWithTools(self, query):
        global rigel
        
        syslog.info(f"QueryWithTools called with query: {query[:100]}...")
        result = asyncio.run(rigel.inference_with_tools(query))
        if hasattr(result, 'content'):
            return result.content
        else:
            return str(result)


if __name__ == "__main__":
    print("RIGEL Experimental DBUS Interface")
    print("Copyright (C) 2025 Zerone Laboratories")
    print("Licensed under GNU Affero General Public License v3.0")
    print("This is free software; see the source for copying conditions.")
    print("")
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
    print("Available Methods:")
    print("  - Query: Basic inference")
    print("  - QueryWithMemory: Inference with conversation memory")
    print("  - QueryThink: Advanced thinking capabilities")
    print("  - QueryWithTools: Inference with MCP tools support")
    print("  - GetLicenseInfo: Display license and copyright information")
    print("Press Ctrl+C to stop")

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nStopping RIGEL D-Bus service...")
        loop.quit()