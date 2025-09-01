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
def read_python_docs(topic: str, module: Optional[str] = None) -> Dict[str, Any]:
    """
    Read Python documentation for a specific topic or module.
    
    Args:
        topic: The topic to search for (e.g., 'list', 'dict', 'file operations', 'regex')
        module: Optional specific module to focus on (e.g., 'os', 'sys', 'json', 'requests')
    
    Returns:
        Dictionary containing documentation content and relevant examples
    """
    try:
        # First try to get help from the Python interpreter
        if module:
            try:
                help_command = f"python3 -c \"import {module}; help({module})\""
                if topic and topic != module:
                    help_command = f"python3 -c \"import {module}; help({module}.{topic})\""
            except:
                help_command = f"python3 -c \"help('{topic}')\""
        else:
            help_command = f"python3 -c \"help('{topic}')\""
        
        result = subprocess.run(
            help_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        local_docs = result.stdout if result.returncode == 0 else ""
        
        # Also try to fetch from online Python documentation
        online_docs = ""
        try:
            if module:
                url = f"https://docs.python.org/3/library/{module}.html"
            else:
                # Search the general Python documentation
                search_url = f"https://docs.python.org/3/search.html?q={topic}"
                url = f"https://docs.python.org/3/tutorial/index.html"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            request = Request(url, headers=headers)
            with urlopen(request, timeout=10) as response:
                content = response.read().decode('utf-8')
                # Extract relevant text content (basic HTML parsing)
                # Remove HTML tags for basic text extraction
                text_content = re.sub(r'<[^>]+>', '', content)
                # Get relevant sections
                lines = text_content.split('\n')
                relevant_lines = []
                for i, line in enumerate(lines):
                    if topic.lower() in line.lower():
                        # Include context around the match
                        start = max(0, i-3)
                        end = min(len(lines), i+10)
                        relevant_lines.extend(lines[start:end])
                        relevant_lines.append("---")
                
                online_docs = '\n'.join(relevant_lines[:1000])  # Limit size
        except Exception as e:
            online_docs = f"Could not fetch online docs: {str(e)}"
        
        # Try to provide practical examples
        examples = ""
        if OS_TOOLS_AVAILABLE:
            example_code = f"""
# Quick example for {topic}
try:
    print("=== {topic} Examples ===")
"""
            if module:
                example_code += f"    import {module}\n"
                example_code += f"    print(dir({module}))\n"
            
            if topic in ['list', 'dict', 'string', 'int', 'float']:
                example_code += f"""
    # Basic {topic} operations
    example = {topic}()
    print(f"Type: {{type(example)}}")
    print(f"Methods: {{[m for m in dir(example) if not m.startswith('_')][:10]}}")
"""
            
            example_code += """
except Exception as e:
    print(f"Error: {e}")
"""
            
            try:
                example_result = os_tools.create_and_execute_program(
                    content=example_code,
                    timeout=10,
                    cleanup=True
                )
                if example_result["success"]:
                    examples = example_result["stdout"]
            except:
                pass
        
        return {
            "success": True,
            "topic": topic,
            "module": module,
            "local_help": local_docs[:2000],  # Limit size
            "online_docs": online_docs[:1000],  # Limit size
            "examples": examples,
            "suggestions": [
                f"Try: help({topic})" if not module else f"Try: help({module}.{topic})",
                f"Check: https://docs.python.org/3/library/{module}.html" if module else f"Search: https://docs.python.org/3/search.html?q={topic}",
                "Use dir() to explore object attributes",
                "Check __doc__ attribute for docstrings"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "topic": topic,
            "module": module
        }


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
def read_ubuntu_docs(topic: str, version: Optional[str] = None) -> Dict[str, Any]:
    """
    Read Ubuntu-specific documentation and information.
    
    Args:
        topic: The topic to search for (e.g., 'apt', 'systemd', 'networking', 'security')
        version: Optional Ubuntu version (e.g., '22.04', '20.04')
    
    Returns:
        Dictionary containing Ubuntu documentation and system information
    """
    try:
        # Get Ubuntu version info
        version_info = ""
        try:
            lsb_result = subprocess.run(
                "lsb_release -a",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            if lsb_result.returncode == 0:
                version_info = lsb_result.stdout
        except:
            pass
        
        # Try to get relevant apt information if topic is package-related
        apt_info = ""
        if topic in ['apt', 'package', 'install', 'update']:
            try:
                apt_commands = [
                    "apt list --installed | head -5",
                    "apt list --upgradable | head -5",
                    "apt-cache policy"
                ]
                
                apt_results = []
                for cmd in apt_commands:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        apt_results.append(f"$ {cmd}\n{result.stdout[:300]}")
                
                apt_info = "\n\n".join(apt_results)
            except:
                pass
        
        # Try to get service information if topic is service-related
        service_info = ""
        if topic in ['systemd', 'service', 'daemon', 'startup']:
            try:
                service_commands = [
                    "systemctl list-units --type=service --state=running | head -10",
                    "systemctl list-unit-files --type=service --state=enabled | head -10"
                ]
                
                service_results = []
                for cmd in service_commands:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        service_results.append(f"$ {cmd}\n{result.stdout[:400]}")
                
                service_info = "\n\n".join(service_results)
            except:
                pass
        
        # Try to get network information if topic is network-related
        network_info = ""
        if topic in ['network', 'networking', 'ip', 'interface']:
            try:
                network_commands = [
                    "ip addr show | head -20",
                    "ip route show | head -10",
                    "ss -tuln | head -10"
                ]
                
                network_results = []
                for cmd in network_commands:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        network_results.append(f"$ {cmd}\n{result.stdout[:300]}")
                
                network_info = "\n\n".join(network_results)
            except:
                pass
        
        # Get general system information
        system_info = ""
        if OS_TOOLS_AVAILABLE:
            sys_result = os_tools.get_detailed_system_info()
            if sys_result["success"]:
                system_info = json.dumps(sys_result["info"], indent=2)
        
        # Try to find relevant configuration files
        config_info = ""
        config_locations = {
            'apt': ['/etc/apt/sources.list', '/etc/apt/sources.list.d/'],
            'network': ['/etc/netplan/', '/etc/network/interfaces'],
            'systemd': ['/etc/systemd/system/', '/etc/systemd/user/'],
            'security': ['/etc/security/', '/etc/sudoers'],
            'ssh': ['/etc/ssh/sshd_config'],
            'cron': ['/etc/cron.d/', '/etc/crontab']
        }
        
        if topic.lower() in config_locations:
            config_files = config_locations[topic.lower()]
            config_results = []
            
            for config_path in config_files:
                try:
                    if os.path.isfile(config_path):
                        result = subprocess.run(
                            f"head -20 {config_path}",
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            config_results.append(f"=== {config_path} ===\n{result.stdout}")
                    elif os.path.isdir(config_path):
                        result = subprocess.run(
                            f"ls -la {config_path}",
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            config_results.append(f"=== {config_path} contents ===\n{result.stdout}")
                except:
                    pass
            
            config_info = "\n\n".join(config_results)
        
        return {
            "success": True,
            "topic": topic,
            "ubuntu_version": version or "current system",
            "version_info": version_info,
            "apt_info": apt_info,
            "service_info": service_info,
            "network_info": network_info,
            "system_info": system_info[:1000] if system_info else "",
            "config_info": config_info[:1500] if config_info else "",
            "suggestions": [
                f"Check Ubuntu docs: https://help.ubuntu.com/",
                f"Try: man {topic}",
                f"Search packages: apt search {topic}",
                f"Check logs: sudo journalctl -u {topic}" if topic not in ['apt', 'package'] else "Check logs: sudo apt log",
                "Use 'ubuntu-bug' to report issues",
                "Check /usr/share/doc/ for package documentation"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "topic": topic,
            "version": version
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
def fetch_webpage_content(url: str, max_length: int = 2000) -> Dict[str, Any]:
    """
    Fetch and extract text content from a webpage.
    
    Args:
        url: The URL to fetch content from
        max_length: Maximum length of content to return (default: 2000)
    
    Returns:
        Dictionary containing webpage content and metadata
    """
    try:
        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return {
                "success": False,
                "error": "Invalid URL format",
                "url": url
            }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        request = Request(url, headers=headers)
        
        with urlopen(request, timeout=15) as response:
            content = response.read()
            
            # Handle different encodings
            encoding = response.headers.get_content_charset() or 'utf-8'
            html_content = content.decode(encoding, errors='ignore')
            
            # Extract title
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
            title = title_match.group(1) if title_match else "No title found"
            title = html.unescape(title).strip()
            
            # Remove script and style elements
            html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            
            # Extract text content by removing HTML tags
            text_content = re.sub(r'<[^>]+>', ' ', html_content)
            
            # Clean up whitespace
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            
            # Unescape HTML entities
            text_content = html.unescape(text_content)
            
            # Truncate if necessary
            if len(text_content) > max_length:
                text_content = text_content[:max_length] + "..."
            
            return {
                "success": True,
                "url": url,
                "title": title,
                "content": text_content,
                "content_length": len(text_content),
                "status_code": response.status,
                "content_type": response.headers.get('Content-Type', 'unknown')
            }
            
    except HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP Error {e.code}: {e.reason}",
            "url": url,
            "status_code": e.code
        }
    except URLError as e:
        return {
            "success": False,
            "error": f"URL Error: {e.reason}",
            "url": url
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


@mcp.tool()
def execute_python_script(code: str, timeout: int = 30, save_output: bool = False, output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute Python code in a temporary script file.
    
    Args:
        code: The Python code to execute
        timeout: Maximum execution time in seconds (default: 30)
        save_output: Whether to save the output to a file (default: False)
        output_file: Optional file path to save output (if save_output is True)
    
    Returns:
        Dictionary containing execution results, output, and any errors
    """
    try:
        # Create a unique temporary file
        script_id = str(uuid.uuid4())[:8]
        temp_script = f"/tmp/rigel_script_{script_id}.py"
        
        # Write the code to the temporary file
        with open(temp_script, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Execute the script
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, temp_script],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp"
        )
        execution_time = time.time() - start_time
        
        # Prepare the result
        execution_result = {
            "success": result.returncode == 0,
            "script_id": script_id,
            "execution_time": round(execution_time, 3),
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "script_path": temp_script,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save output to file if requested
        if save_output and (result.stdout or result.stderr):
            if not output_file:
                output_file = f"/tmp/rigel_output_{script_id}.txt"
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"=== Python Script Execution Results ===\n")
                    f.write(f"Script ID: {script_id}\n")
                    f.write(f"Timestamp: {execution_result['timestamp']}\n")
                    f.write(f"Execution Time: {execution_time:.3f}s\n")
                    f.write(f"Return Code: {result.returncode}\n\n")
                    
                    if result.stdout:
                        f.write("=== STDOUT ===\n")
                        f.write(result.stdout)
                        f.write("\n\n")
                    
                    if result.stderr:
                        f.write("=== STDERR ===\n")
                        f.write(result.stderr)
                        f.write("\n\n")
                    
                    f.write("=== CODE ===\n")
                    f.write(code)
                
                execution_result["output_file"] = output_file
                execution_result["output_saved"] = True
            except Exception as e:
                execution_result["output_save_error"] = str(e)
                execution_result["output_saved"] = False
        
        # Clean up the temporary script file
        try:
            os.remove(temp_script)
            execution_result["script_cleaned"] = True
        except Exception as e:
            execution_result["cleanup_error"] = str(e)
            execution_result["script_cleaned"] = False
        
        return execution_result
        
    except subprocess.TimeoutExpired:
        # Clean up on timeout
        try:
            os.remove(temp_script)
        except:
            pass
        
        return {
            "success": False,
            "error": f"Script execution timed out after {timeout} seconds",
            "script_id": script_id,
            "timeout": timeout,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        # Clean up on error
        try:
            os.remove(temp_script)
        except:
            pass
        
        return {
            "success": False,
            "error": str(e),
            "script_id": script_id,
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
def install_python_library(package_name: str, version: Optional[str] = None, upgrade: bool = False, user_install: bool = True, extra_args: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Install Python libraries using pip.
    
    Args:
        package_name: Name of the package to install (e.g., 'requests', 'numpy')
        version: Optional specific version to install (e.g., '2.28.1')
        upgrade: Whether to upgrade the package if already installed (default: False)
        user_install: Whether to install for user only (--user flag) (default: True)
        extra_args: Optional list of additional pip arguments
    
    Returns:
        Dictionary containing installation results and package information
    """
    try:
        # Build the pip command
        pip_cmd = [sys.executable, "-m", "pip", "install"]
        
        # Add user flag if requested
        if user_install:
            pip_cmd.append("--user")
        
        # Add upgrade flag if requested
        if upgrade:
            pip_cmd.append("--upgrade")
        
        # Build package specification
        if version:
            package_spec = f"{package_name}=={version}"
        else:
            package_spec = package_name
        
        pip_cmd.append(package_spec)
        
        # Add any extra arguments
        if extra_args:
            pip_cmd.extend(extra_args)
        
        # Execute the installation
        start_time = time.time()
        result = subprocess.run(
            pip_cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for installations
            cwd="/tmp"
        )
        execution_time = time.time() - start_time
        
        # Check if installation was successful
        success = result.returncode == 0
        
        # Try to get package information after installation
        package_info = {}
        if success:
            try:
                # Get package version and location
                show_result = subprocess.run(
                    [sys.executable, "-m", "pip", "show", package_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if show_result.returncode == 0:
                    # Parse pip show output
                    for line in show_result.stdout.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            package_info[key.strip().lower().replace('-', '_')] = value.strip()
                
                # Test import
                import_test_result = subprocess.run(
                    [sys.executable, "-c", f"import {package_name}; print(f'Successfully imported {package_name}')"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                package_info["import_test_success"] = import_test_result.returncode == 0
                package_info["import_test_output"] = import_test_result.stdout if import_test_result.returncode == 0 else import_test_result.stderr
                
            except Exception as e:
                package_info["info_error"] = str(e)
        
        return {
            "success": success,
            "package_name": package_name,
            "version_requested": version,
            "package_spec": package_spec,
            "execution_time": round(execution_time, 3),
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": " ".join(pip_cmd),
            "user_install": user_install,
            "upgrade": upgrade,
            "package_info": package_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Package installation timed out after 5 minutes",
            "package_name": package_name,
            "version_requested": version,
            "timeout": 300,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "package_name": package_name,
            "version_requested": version,
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
def list_installed_packages(search_pattern: Optional[str] = None, include_system: bool = False) -> Dict[str, Any]:
    """
    List installed Python packages.
    
    Args:
        search_pattern: Optional pattern to filter packages (case-insensitive)
        include_system: Whether to include system packages (default: False, shows only user packages)
    
    Returns:
        Dictionary containing list of installed packages with their versions
    """
    try:
        # Build pip list command
        pip_cmd = [sys.executable, "-m", "pip", "list"]
        
        if not include_system:
            pip_cmd.append("--user")
        
        # Execute pip list
        result = subprocess.run(
            pip_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": "Failed to list packages",
                "stderr": result.stderr,
                "command": " ".join(pip_cmd)
            }
        
        # Parse the output
        packages = []
        lines = result.stdout.strip().split('\n')
        
        # Skip header lines
        for line in lines[2:]:  # Usually first two lines are headers
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    package_name = parts[0]
                    version = parts[1]
                    
                    # Apply search filter if provided
                    if search_pattern is None or search_pattern.lower() in package_name.lower():
                        packages.append({
                            "name": package_name,
                            "version": version
                        })
        
        # Get additional info about Python environment
        env_info = {}
        try:
            env_info["python_version"] = platform.python_version()
            env_info["python_executable"] = sys.executable
            
            # Get pip version
            pip_version_result = subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if pip_version_result.returncode == 0:
                env_info["pip_version"] = pip_version_result.stdout.strip()
                
        except Exception as e:
            env_info["info_error"] = str(e)
        
        return {
            "success": True,
            "packages": packages,
            "total_packages": len(packages),
            "search_pattern": search_pattern,
            "include_system": include_system,
            "environment_info": env_info,
            "command": " ".join(pip_cmd),
            "timestamp": datetime.now().isoformat()
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Package listing timed out after 30 seconds",
            "search_pattern": search_pattern,
            "include_system": include_system,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "search_pattern": search_pattern,
            "include_system": include_system,
            "timestamp": datetime.now().isoformat()
        }



if __name__ == "__main__":
    mcp.run(transport="sse")
