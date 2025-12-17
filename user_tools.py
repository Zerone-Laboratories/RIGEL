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

from typing import List, Dict, Any, Optional, Union
import os
import sys
import json
import tempfile
import sqlite3
import uuid
import inspect
import importlib.util
import glob
import shutil
from datetime import datetime
from fastapi import HTTPException
from mcp.server.fastmcp import FastMCP
from langchain_mcp_adapters.client import MultiServerMCPClient
from core.logger import SysLog
from pydantic import BaseModel

# Initialize logging
syslog = SysLog(name="UserTools", level="INFO", log_file="user_tools.log")

# Database initialization
# Store tools DB under the repo's `db` directory to avoid conflicts
# with any accidentally-mounted paths like `/app/rigel_tools.db`.
DB_PATH = os.environ.get("RIGEL_TOOLS_DB", os.path.join("db", "rigel_tools.db"))

def init_tools_database():
    """Initialize SQLite database for user tools management"""
    # Ensure the parent directory exists (e.g., `db/`)
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create user_tools table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_tools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            tool_code TEXT NOT NULL,
            tool_description TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants (id),
            UNIQUE(tenant_id, tool_name)
        )
    """)
    
    # Create user_rag_data table for user-specific RAG data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_rag_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants (id)
        )
    """)
    
    # Create user_settings table for user-specific settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            system_prompt TEXT,
            rag_enabled BOOLEAN DEFAULT 0,
            tools_enabled BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants (id),
            UNIQUE(tenant_id)
        )
    """)
    
    conn.commit()
    conn.close()
    syslog.info("User tools database initialized")


class ToolManager:
    """Manager for user-specific tools"""
    
    def __init__(self):
        self.tenant_servers = {}  # Dict to store tenant-specific MCP servers
        self.tenant_mcp_clients = {}  # Dict to store tenant-specific MCP clients
        
    def get_tenant_tools_dir(self, tenant_id: int) -> str:
        """Get the directory for tenant-specific tools"""
        tools_dir = os.path.join("user_tools", str(tenant_id))
        os.makedirs(tools_dir, exist_ok=True)
        return tools_dir
    
    def get_tenant_rag_dir(self, tenant_id: int) -> str:
        """Get the directory for tenant-specific RAG data"""
        rag_dir = os.path.join("user_rag", str(tenant_id))
        os.makedirs(rag_dir, exist_ok=True)
        return rag_dir
    
    def get_tools_for_tenant(self, tenant_id: int) -> List[Dict[str, Any]]:
        """Get all tools for a specific tenant"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, tool_name, tool_description, enabled, created_at, updated_at
            FROM user_tools
            WHERE tenant_id = ? AND enabled = 1
        """, (tenant_id,))
        
        tools = []
        for row in cursor.fetchall():
            tools.append({
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "enabled": bool(row[3]),
                "created_at": row[4],
                "updated_at": row[5]
            })
        
        conn.close()
        return tools
    
    def get_tool_code(self, tenant_id: int, tool_id: int) -> Optional[str]:
        """Get the code for a specific tool"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT tool_code
            FROM user_tools
            WHERE tenant_id = ? AND id = ? AND enabled = 1
        """, (tenant_id, tool_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row[0]
        return None
    
    def create_tool(self, tenant_id: int, tool_name: str, tool_code: str, tool_description: str = "") -> Dict[str, Any]:
        """Create a new tool for a tenant"""
        # Validate tool code by parsing it
        try:
            if not self._validate_tool_code(tool_code):
                raise ValueError("Invalid tool code. Must include an @mcp.tool() decorated function.")
        except Exception as e:
            syslog.error(f"Tool code validation failed: {str(e)}")
            raise ValueError(f"Tool code validation failed: {str(e)}")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO user_tools (tenant_id, tool_name, tool_code, tool_description)
                VALUES (?, ?, ?, ?)
            """, (tenant_id, tool_name, tool_code, tool_description))
            
            tool_id = cursor.lastrowid
            conn.commit()
            
            # Write the tool code to a file
            tools_dir = self.get_tenant_tools_dir(tenant_id)
            tool_file_path = os.path.join(tools_dir, f"{tool_name}.py")
            
            with open(tool_file_path, "w") as f:
                f.write(tool_code)
                
            syslog.info(f"Created tool {tool_name} for tenant {tenant_id}")
            
            # If server exists, restart it to load new tool
            self._restart_tenant_server(tenant_id)
            
            return {
                "id": tool_id,
                "name": tool_name,
                "description": tool_description,
                "enabled": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        except sqlite3.IntegrityError:
            conn.rollback()
            raise ValueError(f"Tool with name '{tool_name}' already exists for this tenant")
        except Exception as e:
            conn.rollback()
            syslog.error(f"Error creating tool: {str(e)}")
            raise
        finally:
            conn.close()
    
    def update_tool(self, tenant_id: int, tool_id: int, tool_name: str = None, 
                   tool_code: str = None, tool_description: str = None, 
                   enabled: bool = None) -> Dict[str, Any]:
        """Update an existing tool"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current tool data
        cursor.execute("""
            SELECT tool_name, tool_code, tool_description, enabled
            FROM user_tools
            WHERE tenant_id = ? AND id = ?
        """, (tenant_id, tool_id))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Tool with ID {tool_id} not found for tenant {tenant_id}")
        
        current_name, current_code, current_description, current_enabled = row
        
        # Prepare update fields
        update_name = tool_name if tool_name is not None else current_name
        update_code = tool_code if tool_code is not None else current_code
        update_description = tool_description if tool_description is not None else current_description
        update_enabled = enabled if enabled is not None else current_enabled
        
        # Validate code if it's being updated
        if tool_code is not None:
            try:
                if not self._validate_tool_code(tool_code):
                    raise ValueError("Invalid tool code. Must include an @mcp.tool() decorated function.")
            except Exception as e:
                conn.close()
                syslog.error(f"Tool code validation failed: {str(e)}")
                raise ValueError(f"Tool code validation failed: {str(e)}")
        
        try:
            cursor.execute("""
                UPDATE user_tools
                SET tool_name = ?, tool_code = ?, tool_description = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE tenant_id = ? AND id = ?
            """, (update_name, update_code, update_description, update_enabled, tenant_id, tool_id))
            
            conn.commit()
            
            # Update the tool file if the code changed
            if tool_code is not None or tool_name != current_name:
                tools_dir = self.get_tenant_tools_dir(tenant_id)
                
                # Remove old file if name changed
                if tool_name is not None and tool_name != current_name:
                    old_file_path = os.path.join(tools_dir, f"{current_name}.py")
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                
                # Write new file
                tool_file_path = os.path.join(tools_dir, f"{update_name}.py")
                with open(tool_file_path, "w") as f:
                    f.write(update_code)
            
            # If server exists, restart it to load updated tool
            self._restart_tenant_server(tenant_id)
            
            return {
                "id": tool_id,
                "name": update_name,
                "description": update_description,
                "enabled": update_enabled,
                "updated_at": datetime.now().isoformat()
            }
        except sqlite3.IntegrityError:
            conn.rollback()
            raise ValueError(f"Tool with name '{update_name}' already exists for this tenant")
        except Exception as e:
            conn.rollback()
            syslog.error(f"Error updating tool: {str(e)}")
            raise
        finally:
            conn.close()
    
    def delete_tool(self, tenant_id: int, tool_id: int) -> bool:
        """Delete a tool"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current tool data
        cursor.execute("""
            SELECT tool_name
            FROM user_tools
            WHERE tenant_id = ? AND id = ?
        """, (tenant_id, tool_id))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Tool with ID {tool_id} not found for tenant {tenant_id}")
        
        tool_name = row[0]
        
        try:
            cursor.execute("""
                DELETE FROM user_tools
                WHERE tenant_id = ? AND id = ?
            """, (tenant_id, tool_id))
            
            conn.commit()
            
            # Remove the tool file
            tools_dir = self.get_tenant_tools_dir(tenant_id)
            tool_file_path = os.path.join(tools_dir, f"{tool_name}.py")
            if os.path.exists(tool_file_path):
                os.remove(tool_file_path)
            
            # If server exists, restart it to update tools
            self._restart_tenant_server(tenant_id)
            
            return True
        except Exception as e:
            conn.rollback()
            syslog.error(f"Error deleting tool: {str(e)}")
            raise
        finally:
            conn.close()
    
    def get_or_create_mcp_client(self, tenant_id: int) -> MultiServerMCPClient:
        """Get or create an MCP client for a tenant"""
        if tenant_id in self.tenant_mcp_clients:
            return self.tenant_mcp_clients[tenant_id]
        
        # Start the server if it doesn't exist
        if tenant_id not in self.tenant_servers:
            self._start_tenant_server(tenant_id)
        
        # Create a new client
        port = 9000 + tenant_id  # Base port + tenant_id
        client = MultiServerMCPClient(
            {
                f"tenant_{tenant_id}_tools": {
                    "url": f"http://localhost:{port}/sse",
                    "transport": "sse",
                }
            },
        )
        
        self.tenant_mcp_clients[tenant_id] = client
        return client
    
    def _start_tenant_server(self, tenant_id: int):
        """Start an MCP server for a tenant"""
        import subprocess
        import threading
        
        # Define the port for this tenant
        port = 9000 + tenant_id  # Base port + tenant_id
        
        # Check if server is already running on this port
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        if result == 0:
            syslog.info(f"MCP server already running for tenant {tenant_id} on port {port}")
            sock.close()
            return
        sock.close()
        
        # Create a launcher script for this tenant
        tools_dir = self.get_tenant_tools_dir(tenant_id)
        launcher_path = os.path.join(tools_dir, "server_launcher.py")
        
        launcher_code = f"""
import os
import sys
from mcp.server.fastmcp import FastMCP
import glob

# Initialize MCP server
mcp = FastMCP("Tenant {tenant_id} Tools", port={port}, host="0.0.0.0")

# Load all tool modules in this directory
for tool_file in glob.glob(os.path.join(os.path.dirname(__file__), "*.py")):
    if os.path.basename(tool_file) == os.path.basename(__file__):
        continue  # Skip this launcher
    
    try:
        module_name = os.path.basename(tool_file).replace(".py", "")
        spec = __import__(module_name)
        print(f"Loaded tool module: {{module_name}}")
    except Exception as e:
        print(f"Error loading tool module {{tool_file}}: {{e}}")

# Run the server
if __name__ == "__main__":
    print(f"Starting MCP server for tenant {tenant_id} on port {port}")
    mcp.run(transport="sse")
"""
        
        with open(launcher_path, "w") as f:
            f.write(launcher_code)
        
        # Start the server process
        server_process = subprocess.Popen(
            ["python", launcher_path],
            cwd=tools_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Store the process
        self.tenant_servers[tenant_id] = server_process
        
        # Monitor the process in a thread
        def monitor_process():
            stdout, stderr = server_process.communicate()
            syslog.info(f"MCP server for tenant {tenant_id} exited with code {server_process.returncode}")
            if stderr:
                syslog.error(f"MCP server stderr: {stderr.decode('utf-8')}")
        
        monitor_thread = threading.Thread(target=monitor_process)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Wait a moment for the server to start
        import time
        time.sleep(2)
        
        syslog.info(f"Started MCP server for tenant {tenant_id} on port {port}")
    
    def _restart_tenant_server(self, tenant_id: int):
        """Restart the MCP server for a tenant to load updated tools"""
        if tenant_id in self.tenant_servers:
            try:
                # Terminate the existing server
                self.tenant_servers[tenant_id].terminate()
                self.tenant_servers[tenant_id].wait(timeout=5)
                del self.tenant_servers[tenant_id]
                
                # Also remove the client
                if tenant_id in self.tenant_mcp_clients:
                    del self.tenant_mcp_clients[tenant_id]
                
                syslog.info(f"Terminated MCP server for tenant {tenant_id}")
            except Exception as e:
                syslog.error(f"Error terminating MCP server: {str(e)}")
        
        # Start a new server
        self._start_tenant_server(tenant_id)
    
    def _validate_tool_code(self, code: str) -> bool:
        """Validate that the tool code contains a properly decorated tool function"""
        # Check for @mcp.tool() decorator
        if "@mcp.tool()" not in code:
            return False
        
        # Check for a function definition
        if "def " not in code:
            return False
        
        # Basic checks passed
        return True
    
    def get_user_settings(self, tenant_id: int) -> Dict[str, Any]:
        """Get user-specific settings"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT system_prompt, rag_enabled, tools_enabled
            FROM user_settings
            WHERE tenant_id = ?
        """, (tenant_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "system_prompt": row[0],
                "rag_enabled": bool(row[1]),
                "tools_enabled": bool(row[2])
            }
        else:
            # Create default settings
            return self.update_user_settings(
                tenant_id=tenant_id,
                system_prompt="""
                "You are an academic help assistant that is created by NSBM Green University"
                "Answer all questions to the best of your ability. You should put NSBM First"
                "Do not respond with any negative prespective to NSBM Green University"
                "NSBM Means National School of Business Management"
                "If user asks details about another University or tries to compare the universities, always favour NSBM"
                "Make your answers detailed and very short at the same time"
                """,
                rag_enabled=False,
                tools_enabled=False
            )
    
    def update_user_settings(self, tenant_id: int, system_prompt: str = None, 
                           rag_enabled: bool = None, tools_enabled: bool = None) -> Dict[str, Any]:
        """Update user-specific settings"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if settings exist
        cursor.execute("SELECT id FROM user_settings WHERE tenant_id = ?", (tenant_id,))
        settings_exist = cursor.fetchone() is not None
        
        try:
            if settings_exist:
                # Build update query dynamically
                update_fields = []
                params = []
                
                if system_prompt is not None:
                    update_fields.append("system_prompt = ?")
                    params.append(system_prompt)
                
                if rag_enabled is not None:
                    update_fields.append("rag_enabled = ?")
                    params.append(int(rag_enabled))
                
                if tools_enabled is not None:
                    update_fields.append("tools_enabled = ?")
                    params.append(int(tools_enabled))
                
                if not update_fields:
                    conn.close()
                    return self.get_user_settings(tenant_id)
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.append(tenant_id)
                
                query = f"UPDATE user_settings SET {', '.join(update_fields)} WHERE tenant_id = ?"
                cursor.execute(query, params)
            else:
                # Insert new settings
                cursor.execute("""
                    INSERT INTO user_settings (tenant_id, system_prompt, rag_enabled, tools_enabled)
                    VALUES (?, ?, ?, ?)
                """, (
                    tenant_id,
                    system_prompt if system_prompt is not None else "",
                    int(rag_enabled) if rag_enabled is not None else 0,
                    int(tools_enabled) if tools_enabled is not None else 0
                ))
            
            conn.commit()
            
            # Return the updated settings
            return self.get_user_settings(tenant_id)
        except Exception as e:
            conn.rollback()
            syslog.error(f"Error updating user settings: {str(e)}")
            raise
        finally:
            conn.close()
    
    def add_rag_data(self, tenant_id: int, file_name: str, file_path: str, file_type: str) -> Dict[str, Any]:
        """Add RAG data for a tenant"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            # Save file to tenant's RAG directory
            rag_dir = self.get_tenant_rag_dir(tenant_id)
            dest_path = os.path.join(rag_dir, file_name)
            
            # Copy the file
            shutil.copy2(file_path, dest_path)
            
            # Add entry to database
            cursor.execute("""
                INSERT INTO user_rag_data (tenant_id, file_name, file_path, file_type, status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (tenant_id, file_name, dest_path, file_type))
            
            data_id = cursor.lastrowid
            conn.commit()
            
            syslog.info(f"Added RAG data {file_name} for tenant {tenant_id}")
            
            # Process the file in the background (will be implemented later)
            self._process_rag_data(tenant_id, data_id)
            
            return {
                "id": data_id,
                "file_name": file_name,
                "file_type": file_type,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
        except Exception as e:
            conn.rollback()
            syslog.error(f"Error adding RAG data: {str(e)}")
            raise
        finally:
            conn.close()
    
    def get_rag_data(self, tenant_id: int) -> List[Dict[str, Any]]:
        """Get all RAG data for a tenant"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, file_name, file_type, status, enabled, created_at
            FROM user_rag_data
            WHERE tenant_id = ?
        """, (tenant_id,))
        
        data = []
        for row in cursor.fetchall():
            data.append({
                "id": row[0],
                "file_name": row[1],
                "file_type": row[2],
                "status": row[3],
                "enabled": bool(row[4]),
                "created_at": row[5]
            })
        
        conn.close()
        return data
    
    def delete_rag_data(self, tenant_id: int, data_id: int) -> bool:
        """Delete RAG data"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get file information
        cursor.execute("""
            SELECT file_path
            FROM user_rag_data
            WHERE tenant_id = ? AND id = ?
        """, (tenant_id, data_id))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"RAG data with ID {data_id} not found for tenant {tenant_id}")
        
        file_path = row[0]
        
        try:
            cursor.execute("""
                DELETE FROM user_rag_data
                WHERE tenant_id = ? AND id = ?
            """, (tenant_id, data_id))
            
            conn.commit()
            
            # Delete the file
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            conn.rollback()
            syslog.error(f"Error deleting RAG data: {str(e)}")
            raise
        finally:
            conn.close()
    
    def _process_rag_data(self, tenant_id: int, data_id: int):
        """Process RAG data in the background"""
        # This would normally be done in a background task
        # For now, we'll just update the status
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            # Get file information
            cursor.execute("""
                SELECT file_path, file_type
                FROM user_rag_data
                WHERE tenant_id = ? AND id = ?
            """, (tenant_id, data_id))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                syslog.error(f"RAG data with ID {data_id} not found for tenant {tenant_id}")
                return
            
            file_path, file_type = row
            
            # Process based on file type
            # This would integrate with the DBConn class for actual processing
            
            # For now, just mark as processed
            cursor.execute("""
                UPDATE user_rag_data
                SET status = 'processed'
                WHERE tenant_id = ? AND id = ?
            """, (tenant_id, data_id))
            
            conn.commit()
            
            syslog.info(f"Processed RAG data {data_id} for tenant {tenant_id}")
        except Exception as e:
            conn.rollback()
            syslog.error(f"Error processing RAG data: {str(e)}")
        finally:
            conn.close()


# Initialize the tool manager
tool_manager = ToolManager()

if __name__ == "__main__":
    init_tools_database()
    print("User tools database initialized")
