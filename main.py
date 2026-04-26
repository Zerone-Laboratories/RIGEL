#!/usr/bin/env python3
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

"""
RIGEL Engine Main Launcher
Allows users to choose between D-Bus server and Web server modes
"""

import os
import sys
import subprocess
from dotenv import load_dotenv
from version import VERSION

def print_banner():
    print("=" * 60)
    print(f"  RIGEL Engine v{VERSION} - Multi-LLM Agentic AI Assistant")
    print("  Copyright (C) 2025 Zerone Laboratories")
    print("  Licensed under GNU Affero General Public License v3.0")
    print("=" * 60)
    print()

def print_menu():
    print("Choose RIGEL server mode:")
    print()
    print("  1. D-Bus Server (Recommended for Linux desktop integration)")
    print("     - System-wide AI assistance")
    print("     - Inter-process communication via D-Bus")
    print("     - Desktop application integration")
    print()
    print("  2. Web Server (HTTP REST API)")
    print("     - Web-based API endpoints")
    print("     - Cross-platform compatibility")
    print("     - Remote access capability")
    print("     - FastAPI with automatic documentation")
    print()
    print("  3. Exit")
    print()

def check_dependencies():
    issues = []

    try:
        import pydbus
        import gi
        dbus_available = True
    except ImportError:
        dbus_available = False
        issues.append("D-Bus support not available (missing pydbus or gi)")

    try:
        import fastapi
        import uvicorn
        web_available = True
    except ImportError:
        web_available = False
        issues.append("Web server support not available (missing fastapi or uvicorn)")

    # Check for core RIGEL dependencies
    try:
        from core.rigel import RigelOllama, RigelGroq
        from core.logger import SysLog
        core_available = True
    except ImportError:
        core_available = False
        issues.append("RIGEL core modules not available")

    return {
        'dbus': dbus_available,
        'web': web_available,
        'core': core_available,
        'issues': issues
    }

def run_dbus_server():
    """Launch the D-Bus server"""
    print("Starting RIGEL D-Bus Server...")
    print("Note: D-Bus server requires Linux with D-Bus support")
    print()

    try:
        subprocess.run([sys.executable, "dbus_server.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error starting D-Bus server: {e}")
        return False
    except KeyboardInterrupt:
        print("\nD-Bus server stopped by user")
        return True

def run_web_server():
    """Launch the Web server"""
    print("Starting RIGEL Web Server...")
    print("Server will be available at: http://localhost:8000")
    print("API documentation will be available at: http://localhost:8000/docs")
    print()

    try:
        subprocess.run([sys.executable, "web_server.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error starting Web server: {e}")
        return False
    except KeyboardInterrupt:
        print("\nWeb server stopped by user")
        return True

def main():
    """Main launcher function"""
    # Load environment from .env so child processes pick up variables in same shell
    load_dotenv()
    print_banner()

    # Check dependencies
    deps = check_dependencies()

    if not deps['core']:
        print(" ERROR: RIGEL core modules are not available!")
        print("Please ensure you have installed the required dependencies:")
        print("  pip install -r requirements.txt")
        print()
        for issue in deps['issues']:
            print(f"  - {issue}")
        sys.exit(1)

    # Show warnings for missing optional dependencies
    if deps['issues']:
        print("  WARNINGS:")
        for issue in deps['issues']:
            print(f"  - {issue}")
        print()

    while True:
        print_menu()

        try:
            choice = input("Enter your choice (1-3): ").strip()
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            sys.exit(0)

        if choice == "1":
            if not deps['dbus']:
                print(" D-Bus server is not available due to missing dependencies.")
                print("Please install D-Bus dependencies:")
                print("  # Ubuntu/Debian:")
                print("  sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0")
                print("  pip install pydbus")
                print()
                print("  # Fedora/RHEL:")
                print("  sudo dnf install python3-gobject python3-gobject-cairo gtk3-devel")
                print("  pip install pydbus")
                print()
                continue

            if run_dbus_server():
                break
            else:
                input("Press Enter to continue...")

        elif choice == "2":
            if not deps['web']:
                print(" Web server is not available due to missing dependencies.")
                print("Please install Web server dependencies:")
                print("  pip install fastapi uvicorn")
                print()
                continue

            if run_web_server():
                break
            else:
                input("Press Enter to continue...")

        elif choice == "3":
            print("Goodbye!")
            sys.exit(0)

        else:
            print(" Invalid choice. Please enter 1, 2, or 3.")
            print()

if __name__ == "__main__":
    main()
