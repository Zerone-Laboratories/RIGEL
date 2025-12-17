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

from typing import List, Dict, Any, Optional, Union
from mcp.server.fastmcp import FastMCP
import subprocess
import os
import sys
import json
import tempfile
import shutil
from datetime import datetime
import platform
import uuid
import re
from urllib.parse import urljoin, urlparse, quote_plus
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional
import time
import html

# Import OSTools class if it's available
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from core.os_tools import OSTools
    os_tools = OSTools()
    OS_TOOLS_AVAILABLE = True
except ImportError:
    print("OSTools module not available. Advanced OS operations will be limited.")
    OS_TOOLS_AVAILABLE = False

mcp = FastMCP("Rigel Tool", port=8001, host="0.0.0.0")


@mcp.tool()
def current_time() -> Dict[str, Any]:
    """Returns the current time."""
    return {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


@mcp.tool()
def read_linux_docs(command: str, section: Optional[str] = None) -> Dict[str, Any]:
    """
    Read Linux/Unix documentation using man pages and other sources.
    
    Args:
        command: The command or topic to look up (e.g., 'ls', 'grep', 'bash', 'systemctl')
        section: Optional man page section (1-8, e.g., '1' for user commands, '5' for file formats)
    
    Returns:
        Dictionary containing man page content and additional information
    """
    try:
        # Try to get man page
        man_command = f"man {section + ' ' if section else ''}{command}"
        
        result = subprocess.run(
            man_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        man_content = result.stdout if result.returncode == 0 else ""
        
        # Also try whatis and apropos for additional info
        whatis_result = subprocess.run(
            f"whatis {command}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        whatis_content = whatis_result.stdout if whatis_result.returncode == 0 else ""
        
        # Try apropos for related commands
        apropos_result = subprocess.run(
            f"apropos {command} | head -10",
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        apropos_content = apropos_result.stdout if apropos_result.returncode == 0 else ""
        
        # Try to get command help if it's available
        help_content = ""
        for help_flag in ['--help', '-h', 'help']:
            help_result = subprocess.run(
                f"{command} {help_flag}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            if help_result.returncode == 0 and help_result.stdout:
                help_content = help_result.stdout
                break
        
        # Try to provide practical examples
        examples = ""
        if OS_TOOLS_AVAILABLE:
            example_commands = []
            
            # Common command examples
            if command == "ls":
                example_commands = ["ls -la", "ls -lh", "ls -lt"]
            elif command == "grep":
                example_commands = ["echo 'hello world' | grep hello", "grep -n 'pattern' /etc/passwd | head -3"]
            elif command == "find":
                example_commands = ["find /tmp -name '*.log' -type f | head -5"]
            elif command == "ps":
                example_commands = ["ps aux | head -5", "ps -ef | head -5"]
            elif command == "df":
                example_commands = ["df -h"]
            elif command == "free":
                example_commands = ["free -h"]
            else:
                # Generic examples
                example_commands = [f"{command} --version 2>/dev/null || echo 'No version info'"]
            
            examples_list = []
            for cmd in example_commands:
                try:
                    cmd_result = os_tools.execute_command(cmd, timeout=5)
                    if cmd_result["success"]:
                        examples_list.append(f"$ {cmd}\n{cmd_result['stdout'][:300]}")
                    else:
                        examples_list.append(f"$ {cmd}\nError: {cmd_result.get('stderr', 'Command failed')[:100]}")
                except:
                    pass
            
            examples = "\n\n".join(examples_list)
        
        return {
            "success": True,
            "command": command,
            "section": section,
            "man_page": man_content[:3000],  # Limit size
            "whatis": whatis_content,
            "related_commands": apropos_content,
            "help_output": help_content[:1000],
            "examples": examples,
            "suggestions": [
                f"Try: man {command}",
                f"Try: {command} --help",
                f"Try: apropos {command}",
                f"Check: https://linux.die.net/man/1/{command}",
                "Use 'man man' to learn about manual sections"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "command": command,
            "section": section
        }


@mcp.tool()
def search_documentation(query: str, doc_type: str = "all") -> Dict[str, Any]:
    """
    Search across multiple documentation sources for a query.
    
    Args:
        query: The search query
        doc_type: Type of documentation to search ("python", "linux", "ubuntu", or "all")
    
    Returns:
        Dictionary containing search results from multiple sources
    """
    try:
        results = {
            "success": True,
            "query": query,
            "doc_type": doc_type,
            "results": {}
        }
        
        if doc_type in ["all", "python"]:
            try:
                python_result = read_python_docs(query)
                results["results"]["python"] = python_result
            except Exception as e:
                results["results"]["python"] = {"error": str(e)}
        
        if doc_type in ["all", "linux"]:
            try:
                linux_result = read_linux_docs(query)
                results["results"]["linux"] = linux_result
            except Exception as e:
                results["results"]["linux"] = {"error": str(e)}
        
        if doc_type in ["all", "ubuntu"]:
            try:
                ubuntu_result = read_ubuntu_docs(query)
                results["results"]["ubuntu"] = ubuntu_result
            except Exception as e:
                results["results"]["ubuntu"] = {"error": str(e)}
        
        # Add some general suggestions
        results["general_suggestions"] = [
            f"Try: apropos {query}",
            f"Search online: https://docs.python.org/3/search.html?q={query}",
            f"Ubuntu help: https://help.ubuntu.com/",
            f"Linux man pages: https://linux.die.net/man/",
            f"Stack Overflow: https://stackoverflow.com/search?q={query}",
            "Use 'which' to find command locations",
            "Use 'type' to identify command types"
        ]
        
        return results
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "doc_type": doc_type
        }


@mcp.tool()
def web_search(query: str, max_results: int = 5, search_engine: str = "duckduckgo") -> Dict[str, Any]:
    """
    Perform a simple web search using only standard library modules.
    
    Args:
        query: The search query
        max_results: Maximum number of results to return (default: 5)
        search_engine: Search engine to use ("duckduckgo", "bing", or "google")
    
    Returns:
        Dictionary containing search results and snippets
    """
    try:
        # URL encode the query
        encoded_query = quote_plus(query)
        
        # Define search URLs for different engines
        search_urls = {
            "duckduckgo": f"https://html.duckduckgo.com/html/?q={encoded_query}",
            "bing": f"https://www.bing.com/search?q={encoded_query}",
            "google": f"https://www.google.com/search?q={encoded_query}"
        }
        
        if search_engine not in search_urls:
            search_engine = "duckduckgo"  # Default fallback
            
        url = search_urls[search_engine]
        
        # Set up headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        # Make the request
        request = Request(url, headers=headers)
        
        with urlopen(request, timeout=15) as response:
            content = response.read()
            
            # Handle gzip encoding if present
            if response.headers.get('Content-Encoding') == 'gzip':
                import gzip
                content = gzip.decompress(content)
                
            html_content = content.decode('utf-8', errors='ignore')
            
            # Parse results based on search engine
            results = []
            
            if search_engine == "duckduckgo":
                results = _parse_duckduckgo_results(html_content, max_results)
            elif search_engine == "bing":
                results = _parse_bing_results(html_content, max_results)
            elif search_engine == "google":
                results = _parse_google_results(html_content, max_results)
            
            return {
                "success": True,
                "query": query,
                "search_engine": search_engine,
                "num_results": len(results),
                "results": results,
                "search_url": url
            }
            
    except HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP Error {e.code}: {e.reason}",
            "query": query,
            "search_engine": search_engine
        }
    except URLError as e:
        return {
            "success": False,
            "error": f"URL Error: {e.reason}",
            "query": query,
            "search_engine": search_engine
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "search_engine": search_engine
        }


def _parse_duckduckgo_results(html_content: str, max_results: int) -> List[Dict[str, str]]:
    """Parse DuckDuckGo search results from HTML content."""
    results = []
    
    # DuckDuckGo result pattern
    result_pattern = r'<div class="result__body">.*?<a rel="nofollow" href="([^"]+)"[^>]*>([^<]+)</a>.*?<a class="result__snippet"[^>]*>([^<]+)</a>'
    
    matches = re.findall(result_pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    for i, (url, title, snippet) in enumerate(matches[:max_results]):
        # Clean up the extracted text
        title = html.unescape(re.sub(r'<[^>]+>', '', title)).strip()
        snippet = html.unescape(re.sub(r'<[^>]+>', '', snippet)).strip()
        
        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "position": i + 1
        })
    
    return results


def _parse_bing_results(html_content: str, max_results: int) -> List[Dict[str, str]]:
    """Parse Bing search results from HTML content."""
    results = []
    
    # Bing result pattern (simplified)
    result_pattern = r'<li class="b_algo">.*?<h2><a href="([^"]+)"[^>]*>([^<]+)</a></h2>.*?<p>([^<]+)</p>'
    
    matches = re.findall(result_pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    for i, (url, title, snippet) in enumerate(matches[:max_results]):
        # Clean up the extracted text
        title = html.unescape(re.sub(r'<[^>]+>', '', title)).strip()
        snippet = html.unescape(re.sub(r'<[^>]+>', '', snippet)).strip()
        
        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "position": i + 1
        })
    
    return results


def _parse_google_results(html_content: str, max_results: int) -> List[Dict[str, str]]:
    """Parse Google search results from HTML content."""
    results = []
    
    # Google result pattern (simplified - Google actively blocks scrapers)
    result_pattern = r'<div class="g">.*?<a href="([^"]+)"[^>]*><h3[^>]*>([^<]+)</h3></a>.*?<span[^>]*>([^<]+)</span>'
    
    matches = re.findall(result_pattern, html_content, re.DOTALL | re.IGNORECASE)
    
    for i, (url, title, snippet) in enumerate(matches[:max_results]):
        # Clean up the extracted text
        title = html.unescape(re.sub(r'<[^>]+>', '', title)).strip()
        snippet = html.unescape(re.sub(r'<[^>]+>', '', snippet)).strip()
        
        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "position": i + 1
        })
    
    return results


@mcp.tool()
def create_qt_ui_component(
    component_type: str,
    properties: Optional[Dict[str, Any]] = None,
    layout_type: Optional[str] = None,
    parent_window: bool = False,
    file_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create Python Qt UI components with comprehensive functionality.
    
    Args:
        component_type: Type of UI component to create
                       Options: "window", "dialog", "widget", "button", "label", "input", 
                               "checkbox", "radio", "combobox", "listbox", "table", "tree",
                               "menu", "toolbar", "statusbar", "tab", "group", "splitter",
                               "scroll", "progress", "slider", "spin", "date", "text_edit",
                               "custom", "full_app"
        properties: Dictionary of component properties (text, size, position, etc.)
        layout_type: Layout manager type ("vertical", "horizontal", "grid", "form", "absolute")
        parent_window: Whether to create as standalone window or widget
        file_path: Optional path to save the generated code
    
    Returns:
        Dictionary containing the generated Qt code and component information
    """
    try:
        if properties is None:
            properties = {}
        
        # Default properties
        default_props = {
            "title": "Qt Application",
            "width": 800,
            "height": 600,
            "x": 100,
            "y": 100,
            "text": "Qt Component",
            "enabled": True,
            "visible": True
        }
        
        # Merge with user properties
        props = {**default_props, **properties}
        
        # Generate imports
        imports = _generate_qt_imports(component_type)
        
        # Generate component code
        component_code = _generate_qt_component(component_type, props, layout_type, parent_window)
        
        # Generate full application code
        full_code = f"""{imports}

{component_code}

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Apply a modern style
    app.setStyle('Fusion')
    
    # Create and show the main component
    window = {_get_main_class_name(component_type)}()
    window.show()
    
    sys.exit(app.exec())
"""
        
        # Save to file if path provided
        if file_path:
            try:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(full_code)
                saved = True
                save_path = os.path.abspath(file_path)
            except Exception as e:
                saved = False
                save_path = f"Error saving: {str(e)}"
        else:
            saved = False
            save_path = None
        
        # Get available methods for the component
        available_methods = _get_qt_component_methods(component_type)
        
        # Get styling examples
        styling_examples = _get_qt_styling_examples(component_type)
        
        return {
            "success": True,
            "component_type": component_type,
            "properties": props,
            "layout_type": layout_type,
            "code": full_code,
            "imports": imports,
            "component_code": component_code,
            "main_class": _get_main_class_name(component_type),
            "saved": saved,
            "file_path": save_path,
            "available_methods": available_methods,
            "styling_examples": styling_examples,
            "usage_tips": _get_qt_usage_tips(component_type),
            "dependencies": ["PyQt6 or PySide6", "sys", "os (optional)"],
            "install_command": "pip install PyQt6  # or pip install PySide6"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "component_type": component_type
        }


def _generate_qt_imports(component_type: str) -> str:
    """Generate appropriate Qt imports based on component type."""
    base_imports = [
        "import sys",
        "from PyQt6.QtWidgets import *",
        "from PyQt6.QtCore import *",
        "from PyQt6.QtGui import *"
    ]
    
    # Add specific imports for certain components
    if component_type in ["date", "calendar"]:
        base_imports.append("from PyQt6.QtWidgets import QCalendarWidget, QDateEdit")
    elif component_type in ["web", "browser"]:
        base_imports.append("from PyQt6.QtWebEngineWidgets import QWebEngineView")
    elif component_type in ["chart", "graph"]:
        base_imports.append("# For charts: pip install PyQtChart")
        base_imports.append("# from PyQt6.QtCharts import *")
    
    return "\n".join(base_imports)


def _generate_qt_component(component_type: str, props: Dict, layout_type: Optional[str], parent_window: bool) -> str:
    """Generate Qt component code based on type and properties."""
    
    class_name = _get_main_class_name(component_type)
    base_class = "QMainWindow" if parent_window or component_type in ["window", "full_app"] else "QWidget"
    
    if component_type == "dialog":
        base_class = "QDialog"
    
    code_parts = []
    
    # Class definition
    code_parts.append(f"class {class_name}({base_class}):")
    code_parts.append("    def __init__(self):")
    code_parts.append("        super().__init__()")
    code_parts.append("        self.initUI()")
    code_parts.append("")
    code_parts.append("    def initUI(self):")
    
    # Set window properties
    if parent_window or component_type in ["window", "dialog", "full_app"]:
        code_parts.append(f"        self.setWindowTitle('{props['title']}')")
        code_parts.append(f"        self.setGeometry({props['x']}, {props['y']}, {props['width']}, {props['height']})")
    
    # Generate component-specific code
    if component_type == "full_app":
        component_code = _generate_full_app_code(props, layout_type)
    elif component_type == "window":
        component_code = _generate_window_code(props, layout_type)
    elif component_type == "dialog":
        component_code = _generate_dialog_code(props, layout_type)
    elif component_type == "button":
        component_code = _generate_button_code(props)
    elif component_type == "label":
        component_code = _generate_label_code(props)
    elif component_type == "input":
        component_code = _generate_input_code(props)
    elif component_type == "table":
        component_code = _generate_table_code(props)
    elif component_type == "tree":
        component_code = _generate_tree_code(props)
    elif component_type == "menu":
        component_code = _generate_menu_code(props)
    elif component_type == "toolbar":
        component_code = _generate_toolbar_code(props)
    elif component_type == "tab":
        component_code = _generate_tab_code(props)
    elif component_type == "text_edit":
        component_code = _generate_text_edit_code(props)
    elif component_type == "progress":
        component_code = _generate_progress_code(props)
    elif component_type == "slider":
        component_code = _generate_slider_code(props)
    else:
        component_code = _generate_generic_component_code(component_type, props, layout_type)
    
    # Add component code with proper indentation
    for line in component_code.split('\n'):
        if line.strip():
            code_parts.append(f"        {line}")
        else:
            code_parts.append("")
    
    # Add event handlers and utility methods
    code_parts.extend(_generate_event_handlers(component_type))
    
    return "\n".join(code_parts)


def _generate_full_app_code(props: Dict, layout_type: Optional[str]) -> str:
    """Generate a complete application with multiple components."""
    return """
# Create central widget and main layout
central_widget = QWidget()
self.setCentralWidget(central_widget)

# Create main layout
if layout_type == 'grid':
    main_layout = QGridLayout()
elif layout_type == 'horizontal':
    main_layout = QHBoxLayout()
else:
    main_layout = QVBoxLayout()

# Create menu bar
self.create_menu_bar()

# Create toolbar
self.create_toolbar()

# Create status bar
self.statusBar().showMessage('Ready')

# Create main content area
self.create_content_area(main_layout)

# Set the layout
central_widget.setLayout(main_layout)

# Apply modern styling
self.setStyleSheet('''
    QMainWindow {
        background-color: #f0f0f0;
    }
    QPushButton {
        background-color: #4CAF50;
        border: none;
        color: white;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #45a049;
    }
    QPushButton:pressed {
        background-color: #3e8e41;
    }
''')
"""


def _generate_window_code(props: Dict, layout_type: Optional[str]) -> str:
    """Generate basic window code."""
    return """
# Create central widget
central_widget = QWidget()
if hasattr(self, 'setCentralWidget'):
    self.setCentralWidget(central_widget)

# Create layout
layout = QVBoxLayout()
central_widget.setLayout(layout)

# Add some example widgets
label = QLabel('Welcome to Qt Application')
label.setAlignment(Qt.AlignmentFlag.AlignCenter)
layout.addWidget(label)

button = QPushButton('Click Me')
button.clicked.connect(self.on_button_click)
layout.addWidget(button)
"""


def _generate_dialog_code(props: Dict, layout_type: Optional[str]) -> str:
    """Generate dialog code."""
    return """
# Create layout
layout = QVBoxLayout()
self.setLayout(layout)

# Add content
label = QLabel('Dialog Content')
layout.addWidget(label)

# Add buttons
button_layout = QHBoxLayout()
ok_button = QPushButton('OK')
cancel_button = QPushButton('Cancel')

ok_button.clicked.connect(self.accept)
cancel_button.clicked.connect(self.reject)

button_layout.addWidget(ok_button)
button_layout.addWidget(cancel_button)
layout.addLayout(button_layout)
"""


def _generate_button_code(props: Dict) -> str:
    """Generate button component code."""
    return f"""
self.button = QPushButton('{props.get('text', 'Button')}')
self.button.clicked.connect(self.on_button_click)

layout = QVBoxLayout()
layout.addWidget(self.button)
self.setLayout(layout)
"""


def _generate_label_code(props: Dict) -> str:
    """Generate label component code."""
    return f"""
self.label = QLabel('{props.get('text', 'Label')}')
self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

layout = QVBoxLayout()
layout.addWidget(self.label)
self.setLayout(layout)
"""


def _generate_input_code(props: Dict) -> str:
    """Generate input field code."""
    return f"""
self.input = QLineEdit()
self.input.setPlaceholderText('{props.get('placeholder', 'Enter text...')}')
self.input.textChanged.connect(self.on_text_changed)

layout = QVBoxLayout()
layout.addWidget(QLabel('Input:'))
layout.addWidget(self.input)
self.setLayout(layout)
"""


def _generate_table_code(props: Dict) -> str:
    """Generate table widget code."""
    return """
self.table = QTableWidget()
self.table.setRowCount(5)
self.table.setColumnCount(3)
self.table.setHorizontalHeaderLabels(['Column 1', 'Column 2', 'Column 3'])

# Add sample data
for row in range(5):
    for col in range(3):
        item = QTableWidgetItem(f'Item {row},{col}')
        self.table.setItem(row, col, item)

layout = QVBoxLayout()
layout.addWidget(self.table)
self.setLayout(layout)
"""


def _generate_tree_code(props: Dict) -> str:
    """Generate tree widget code."""
    return """
self.tree = QTreeWidget()
self.tree.setHeaderLabels(['Name', 'Type', 'Size'])

# Add sample items
root = QTreeWidgetItem(self.tree, ['Root', 'Folder', ''])
child1 = QTreeWidgetItem(root, ['Child 1', 'File', '1KB'])
child2 = QTreeWidgetItem(root, ['Child 2', 'File', '2KB'])
subchild = QTreeWidgetItem(child1, ['Sub Child', 'File', '500B'])

self.tree.expandAll()

layout = QVBoxLayout()
layout.addWidget(self.tree)
self.setLayout(layout)
"""


def _generate_menu_code(props: Dict) -> str:
    """Generate menu bar code."""
    return """
menubar = self.menuBar()

# File menu
file_menu = menubar.addMenu('File')
file_menu.addAction('New', self.new_file, 'Ctrl+N')
file_menu.addAction('Open', self.open_file, 'Ctrl+O')
file_menu.addAction('Save', self.save_file, 'Ctrl+S')
file_menu.addSeparator()
file_menu.addAction('Exit', self.close, 'Ctrl+Q')

# Edit menu
edit_menu = menubar.addMenu('Edit')
edit_menu.addAction('Cut', self.cut, 'Ctrl+X')
edit_menu.addAction('Copy', self.copy, 'Ctrl+C')
edit_menu.addAction('Paste', self.paste, 'Ctrl+V')

# Help menu
help_menu = menubar.addMenu('Help')
help_menu.addAction('About', self.about)
"""


def _generate_toolbar_code(props: Dict) -> str:
    """Generate toolbar code."""
    return """
toolbar = self.addToolBar('Main')
toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

# Add actions
new_action = QAction('New', self)
new_action.triggered.connect(self.new_file)
toolbar.addAction(new_action)

open_action = QAction('Open', self)
open_action.triggered.connect(self.open_file)
toolbar.addAction(open_action)

save_action = QAction('Save', self)
save_action.triggered.connect(self.save_file)
toolbar.addAction(save_action)

toolbar.addSeparator()

exit_action = QAction('Exit', self)
exit_action.triggered.connect(self.close)
toolbar.addAction(exit_action)
"""


def _generate_tab_code(props: Dict) -> str:
    """Generate tab widget code."""
    return """
self.tabs = QTabWidget()

# Create tabs
tab1 = QWidget()
tab1_layout = QVBoxLayout()
tab1_layout.addWidget(QLabel('Content of Tab 1'))
tab1_layout.addWidget(QPushButton('Button in Tab 1'))
tab1.setLayout(tab1_layout)

tab2 = QWidget()
tab2_layout = QVBoxLayout()
tab2_layout.addWidget(QLabel('Content of Tab 2'))
tab2_layout.addWidget(QLineEdit('Input in Tab 2'))
tab2.setLayout(tab2_layout)

tab3 = QWidget()
tab3_layout = QVBoxLayout()
tab3_layout.addWidget(QTextEdit('Text editor in Tab 3'))
tab3.setLayout(tab3_layout)

# Add tabs
self.tabs.addTab(tab1, 'Tab 1')
self.tabs.addTab(tab2, 'Tab 2')
self.tabs.addTab(tab3, 'Tab 3')

layout = QVBoxLayout()
layout.addWidget(self.tabs)
self.setLayout(layout)
"""


def _generate_text_edit_code(props: Dict) -> str:
    """Generate text edit widget code."""
    return """
self.text_edit = QTextEdit()
self.text_edit.setPlainText('Enter your text here...')

# Create toolbar for text formatting
text_toolbar = QHBoxLayout()

bold_btn = QPushButton('Bold')
bold_btn.clicked.connect(self.make_bold)
text_toolbar.addWidget(bold_btn)

italic_btn = QPushButton('Italic')
italic_btn.clicked.connect(self.make_italic)
text_toolbar.addWidget(italic_btn)

underline_btn = QPushButton('Underline')
underline_btn.clicked.connect(self.make_underline)
text_toolbar.addWidget(underline_btn)

layout = QVBoxLayout()
layout.addLayout(text_toolbar)
layout.addWidget(self.text_edit)
self.setLayout(layout)
"""


def _generate_progress_code(props: Dict) -> str:
    """Generate progress bar code."""
    return """
self.progress = QProgressBar()
self.progress.setMinimum(0)
self.progress.setMaximum(100)
self.progress.setValue(0)

self.start_btn = QPushButton('Start Progress')
self.start_btn.clicked.connect(self.start_progress)

self.timer = QTimer()
self.timer.timeout.connect(self.update_progress)

layout = QVBoxLayout()
layout.addWidget(QLabel('Progress Demo:'))
layout.addWidget(self.progress)
layout.addWidget(self.start_btn)
self.setLayout(layout)
"""


def _generate_slider_code(props: Dict) -> str:
    """Generate slider widget code."""
    return """
self.slider = QSlider(Qt.Orientation.Horizontal)
self.slider.setMinimum(0)
self.slider.setMaximum(100)
self.slider.setValue(50)
self.slider.valueChanged.connect(self.on_slider_change)

self.value_label = QLabel('Value: 50')

layout = QVBoxLayout()
layout.addWidget(QLabel('Slider Demo:'))
layout.addWidget(self.slider)
layout.addWidget(self.value_label)
self.setLayout(layout)
"""


def _generate_generic_component_code(component_type: str, props: Dict, layout_type: Optional[str]) -> str:
    """Generate generic component code for unlisted types."""
    layout_code = "QVBoxLayout()" if layout_type != "horizontal" else "QHBoxLayout()"
    
    return f"""
# Generic {component_type} component
layout = {layout_code}

# Add your custom {component_type} implementation here
label = QLabel('Custom {component_type} Component')
label.setAlignment(Qt.AlignmentFlag.AlignCenter)
layout.addWidget(label)

self.setLayout(layout)
"""


def _generate_event_handlers(component_type: str) -> List[str]:
    """Generate common event handler methods."""
    handlers = [
        "",
        "    def on_button_click(self):",
        "        print('Button clicked!')",
        "        # Add your button click logic here",
        "",
    ]
    
    if component_type in ["input", "text_edit"]:
        handlers.extend([
            "    def on_text_changed(self, text):",
            "        print(f'Text changed: {text}')",
            "",
        ])
    
    if component_type == "full_app":
        handlers.extend([
            "    def create_menu_bar(self):",
            "        menubar = self.menuBar()",
            "        file_menu = menubar.addMenu('File')",
            "        file_menu.addAction('Exit', self.close)",
            "",
            "    def create_toolbar(self):",
            "        toolbar = self.addToolBar('Main')",
            "        exit_action = QAction('Exit', self)",
            "        exit_action.triggered.connect(self.close)",
            "        toolbar.addAction(exit_action)",
            "",
            "    def create_content_area(self, layout):",
            "        # Main content area",
            "        content_widget = QWidget()",
            "        content_layout = QVBoxLayout()",
            "        ",
            "        # Add your main content here",
            "        content_layout.addWidget(QLabel('Main Content Area'))",
            "        content_layout.addWidget(QPushButton('Sample Button'))",
            "        ",
            "        content_widget.setLayout(content_layout)",
            "        layout.addWidget(content_widget)",
            "",
            "    def new_file(self):",
            "        print('New file action')",
            "",
            "    def open_file(self):",
            "        print('Open file action')",
            "",
            "    def save_file(self):",
            "        print('Save file action')",
            "",
            "    def cut(self):",
            "        print('Cut action')",
            "",
            "    def copy(self):",
            "        print('Copy action')",
            "",
            "    def paste(self):",
            "        print('Paste action')",
            "",
            "    def about(self):",
            "        QMessageBox.about(self, 'About', 'Qt Application Example')",
            "",
        ])
    
    if component_type == "text_edit":
        handlers.extend([
            "    def make_bold(self):",
            "        cursor = self.text_edit.textCursor()",
            "        format = cursor.charFormat()",
            "        format.setFontWeight(QFont.Weight.Bold if format.fontWeight() != QFont.Weight.Bold else QFont.Weight.Normal)",
            "        cursor.setCharFormat(format)",
            "",
            "    def make_italic(self):",
            "        cursor = self.text_edit.textCursor()",
            "        format = cursor.charFormat()",
            "        format.setFontItalic(not format.fontItalic())",
            "        cursor.setCharFormat(format)",
            "",
            "    def make_underline(self):",
            "        cursor = self.text_edit.textCursor()",
            "        format = cursor.charFormat()",
            "        format.setFontUnderline(not format.fontUnderline())",
            "        cursor.setCharFormat(format)",
            "",
        ])
    
    if component_type == "progress":
        handlers.extend([
            "    def start_progress(self):",
            "        self.progress.setValue(0)",
            "        self.timer.start(100)  # Update every 100ms",
            "        self.start_btn.setEnabled(False)",
            "",
            "    def update_progress(self):",
            "        value = self.progress.value() + 1",
            "        self.progress.setValue(value)",
            "        if value >= 100:",
            "            self.timer.stop()",
            "            self.start_btn.setEnabled(True)",
            "",
        ])
    
    if component_type == "slider":
        handlers.extend([
            "    def on_slider_change(self, value):",
            "        self.value_label.setText(f'Value: {value}')",
            "",
        ])
    
    return handlers


def _get_main_class_name(component_type: str) -> str:
    """Get appropriate class name for component type."""
    names = {
        "window": "MainWindow",
        "dialog": "CustomDialog",
        "full_app": "MainApplication",
        "button": "ButtonWidget",
        "label": "LabelWidget",
        "input": "InputWidget",
        "table": "TableWidget",
        "tree": "TreeWidget",
        "menu": "MenuWindow",
        "toolbar": "ToolbarWindow",
        "tab": "TabWidget",
        "text_edit": "TextEditWidget",
        "progress": "ProgressWidget",
        "slider": "SliderWidget"
    }
    return names.get(component_type, f"{component_type.title()}Widget")


def _get_qt_component_methods(component_type: str) -> Dict[str, List[str]]:
    """Get available methods for Qt component types."""
    common_methods = [
        "show()", "hide()", "setVisible(bool)",
        "setEnabled(bool)", "setToolTip(str)",
        "setStyleSheet(str)", "resize(width, height)",
        "move(x, y)", "setFixedSize(width, height)"
    ]
    
    specific_methods = {
        "window": [
            "setWindowTitle(str)", "setWindowIcon(QIcon)",
            "setCentralWidget(QWidget)", "menuBar()",
            "statusBar()", "addToolBar(str)"
        ],
        "button": [
            "setText(str)", "text()", "clicked.connect(func)",
            "setCheckable(bool)", "isChecked()", "setIcon(QIcon)"
        ],
        "label": [
            "setText(str)", "text()", "setAlignment(Qt.Alignment)",
            "setPixmap(QPixmap)", "setWordWrap(bool)"
        ],
        "input": [
            "setText(str)", "text()", "setPlaceholderText(str)",
            "textChanged.connect(func)", "setEchoMode(QLineEdit.EchoMode)",
            "setValidator(QValidator)"
        ],
        "table": [
            "setRowCount(int)", "setColumnCount(int)",
            "setHorizontalHeaderLabels(list)", "setItem(row, col, QTableWidgetItem)",
            "item(row, col)", "currentRow()", "currentColumn()"
        ],
        "text_edit": [
            "setPlainText(str)", "toPlainText()", "setHtml(str)",
            "toHtml()", "append(str)", "clear()",
            "textChanged.connect(func)"
        ]
    }
    
    return {
        "common": common_methods,
        "specific": specific_methods.get(component_type, [])
    }


def _get_qt_styling_examples(component_type: str) -> Dict[str, str]:
    """Get CSS styling examples for Qt components."""
    
    common_styles = """
/* Common styling */
QWidget {
    font-family: Arial, sans-serif;
    font-size: 12px;
}

QWidget:focus {
    outline: none;
    border: 2px solid #3498db;
}
"""
    
    specific_styles = {
        "button": """
QPushButton {
    background-color: #3498db;
    border: none;
    color: white;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #2980b9;
}

QPushButton:pressed {
    background-color: #21618c;
}

QPushButton:disabled {
    background-color: #bdc3c7;
    color: #7f8c8d;
}
""",
        "input": """
QLineEdit {
    border: 2px solid #bdc3c7;
    border-radius: 4px;
    padding: 8px;
    font-size: 14px;
}

QLineEdit:focus {
    border-color: #3498db;
}

QLineEdit:disabled {
    background-color: #ecf0f1;
    color: #7f8c8d;
}
""",
        "table": """
QTableWidget {
    gridline-color: #bdc3c7;
    background-color: white;
    alternate-background-color: #f8f9fa;
}

QHeaderView::section {
    background-color: #34495e;
    color: white;
    padding: 8px;
    border: none;
    font-weight: bold;
}

QTableWidget::item:selected {
    background-color: #3498db;
    color: white;
}
"""
    }
    
    return {
        "common": common_styles,
        "specific": specific_styles.get(component_type, "/* No specific styles available */")
    }


def _get_qt_usage_tips(component_type: str) -> List[str]:
    """Get usage tips for Qt components."""
    
    common_tips = [
        "Use layouts instead of absolute positioning for responsive design",
        "Always call super().__init__() in your widget constructor",
        "Connect signals to slots for event handling",
        "Use stylesheets for consistent theming",
        "Set object names for easier CSS targeting: widget.setObjectName('myWidget')"
    ]
    
    specific_tips = {
        "window": [
            "Use setCentralWidget() for main content in QMainWindow",
            "Add menus with menuBar().addMenu()",
            "Use statusBar() for status messages",
            "Set window properties before showing"
        ],
        "button": [
            "Use clicked.connect() to handle button presses",
            "Set icons with setIcon(QIcon('path/to/icon.png'))",
            "Make buttons checkable with setCheckable(True)",
            "Use keyboard shortcuts with setShortcut()"
        ],
        "table": [
            "Use QTableWidgetItem for cell content",
            "Enable sorting with setSortingEnabled(True)",
            "Handle selection with selectionChanged signal",
            "Use setSpan() to merge cells"
        ],
        "layout": [
            "QVBoxLayout for vertical arrangement",
            "QHBoxLayout for horizontal arrangement", 
            "QGridLayout for grid arrangement",
            "QFormLayout for form-like layout",
            "Use spacers to control widget spacing"
        ]
    }
    
    all_tips = common_tips.copy()
    all_tips.extend(specific_tips.get(component_type, []))
    
    return all_tips


if __name__ == "__main__":
    mcp.run(transport="sse")
