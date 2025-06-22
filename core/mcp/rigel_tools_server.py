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

from typing import List, Dict, Optional, Set
from mcp.server.fastmcp import FastMCP
import subprocess
import os
import json
import sys
import tempfile
import re
import ast
import importlib
from io import StringIO
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser
import time
# Import DBConn class from the parent directory
# from core.rdb import DBConn

mcp = FastMCP("Rigel Tool", port=8001)


@mcp.tool()
def current_time() -> str:
    """Returns the current time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@mcp.tool()
def run_system_command(command: str, working_directory: str = None) -> str:
    print(command)
    """Run any command on the Linux shell and return the output.
    Provide User's Current working Directory as well
    Args:
        command: The shell command to execute
        working_directory: Optional directory to run the command in (defaults to current directory)
        
    Returns:
        The output of the command or error message with working directory info
    """
    try:
        # Use provided working directory or current directory
        if working_directory:
            if not os.path.exists(working_directory):
                return f"Error: Working directory '{working_directory}' does not exist"
            if not os.path.isdir(working_directory):
                return f"Error: '{working_directory}' is not a directory"
            exec_dir = os.path.abspath(working_directory)
        else:
            exec_dir = os.getcwd()
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=exec_dir
        )
        
        if result.returncode == 0:
            return f"Working directory: {exec_dir}\nCommand succeeded:\n{result.stdout}"
        else:
            return f"Working directory: {exec_dir}\nCommand failed (exit code {result.returncode}):\n{result.stderr}"
            
    except subprocess.TimeoutExpired:
        exec_dir = working_directory if working_directory else os.getcwd()
        return f"Working directory: {exec_dir}\nCommand timed out after 30 seconds"
    except Exception as e:
        exec_dir = working_directory if working_directory else os.getcwd()
        return f"Working directory: {exec_dir}\nError executing command: {str(e)}"

# @mcp.tool()
# def list_directory(directory_path: str = ".") -> str:
#     """List the contents of a directory.
    
#     Args:
#         directory_path: Path to the directory to list (defaults to current directory)
        
#     Returns:
#         List of files and directories or error message
#     """
#     try:
#         items = os.listdir(directory_path)
#         result = []
#         for item in sorted(items):
#             full_path = os.path.join(directory_path, item)
#             if os.path.isdir(full_path):
#                 result.append(f"📁 {item}/")
#             else:
#                 result.append(f"📄 {item}")
#         return "\n".join(result)
#     except Exception as e:
#         return f"Error listing directory: {str(e)}"

@mcp.tool()
def get_system_info() -> str:
    """Get basic system information.
    
    Returns:
        System information as a JSON string
    """
    try:
        info = {
            "current_directory": os.getcwd(),
            "user": os.getenv("USER", "unknown"),
            "home": os.getenv("HOME", "unknown"),
            "shell": os.getenv("SHELL", "unknown"),
            "python_version": subprocess.run(["python3", "--version"], capture_output=True, text=True).stdout.strip()
        }
        return json.dumps(info, indent=2)
    except Exception as e:
        return f"Error getting system info: {str(e)}"

@mcp.tool()
def python_interpreter(query: str) -> str:
    """Execute Python code and return the output. Automatically installs missing packages.
    
    Args:
        query: The Python code to execute
        
    Returns:
        The output of the Python code execution or error message
    """
    import re
    import ast
    import importlib
    
    def extract_imports(code):
        """Extract import statements from Python code."""
        imports = set()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except:
            # Fallback to regex if AST parsing fails
            import_lines = re.findall(r'^(?:from\s+(\w+)|import\s+(\w+))', code, re.MULTILINE)
            for line in import_lines:
                module = line[0] or line[1]
                if module:
                    imports.add(module.split('.')[0])
        return imports
    
    def install_package(package_name):
        """Install a package using pip."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0, result.stdout + result.stderr
        except:
            return False, f"Failed to install {package_name}"
    
    def check_and_install_modules(imports):
        """Check if modules are available and install if missing."""
        installation_log = []
        builtin_modules = set(sys.builtin_module_names)
        standard_library = {
            'os', 'sys', 'json', 'datetime', 'subprocess', 're', 'ast', 'importlib',
            'math', 'random', 'time', 'collections', 'itertools', 'functools',
            'pathlib', 'urllib', 'http', 'email', 'html', 'xml', 'csv', 'sqlite3',
            'threading', 'multiprocessing', 'asyncio', 'logging', 'unittest',
            'tempfile', 'io', 'typing', 'copy', 'pickle', 'base64', 'hashlib',
            'hmac', 'secrets', 'uuid', 'platform', 'shutil', 'glob', 'fnmatch'
        }
        
        for module_name in imports:
            if module_name in builtin_modules or module_name in standard_library:
                continue
                
            try:
                importlib.import_module(module_name)
            except ImportError:
                installation_log.append(f"Installing missing package: {module_name}")
                success, output = install_package(module_name)
                if success:
                    installation_log.append(f"✓ Successfully installed {module_name}")
                else:
                    installation_log.append(f"✗ Failed to install {module_name}: {output}")
        
        return installation_log
    
    try:
        import tempfile
        import sys
        from io import StringIO
        
        # Extract and install required modules
        imports = extract_imports(query)
        installation_log = check_and_install_modules(imports)
        
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            # Enhanced execution environment with more modules
            exec_globals = {
                '__builtins__': __builtins__,
                'os': os,
                'json': json,
                'datetime': datetime,
                'subprocess': subprocess,
                'sys': sys,
                're': re,
                'ast': ast,
                'importlib': importlib,
            }
            
            exec(query, exec_globals)
        
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
            result = ""
            
            # Add installation log if any packages were installed
            if installation_log:
                result += "Package Installation:\n" + "\n".join(installation_log) + "\n\n"
            
            if stdout_output:
                result += f"Output:\n{stdout_output}"
            if stderr_output:
                if result and not result.endswith("\n\n"):
                    result += f"\nErrors/Warnings:\n{stderr_output}"
                else:
                    result += f"Errors/Warnings:\n{stderr_output}"
            
            return result if result else "Code executed successfully (no output)"
            
        except Exception as e:
            # Restore stdout and stderr in case of exception
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
            error_msg = str(e)
            # Check if it's a missing module error and suggest installation
            if "No module named" in error_msg:
                module_match = re.search(r"No module named '(\w+)'", error_msg)
                if module_match:
                    missing_module = module_match.group(1)
                    return f"Error executing Python code: {error_msg}\n\nTrying to install missing module automatically...\n" + \
                           f"Run: pip install {missing_module}"
            
            return f"Error executing Python code: {error_msg}"
            
    except Exception as e:
        return f"Error setting up Python interpreter: {str(e)}"

@mcp.tool()
def search_database(query: str) -> str:
    """Search the database for similar content using the query.
    
    Args:
        query: The search query to find similar content
        
    Returns:
        Retrieved similar content or error message
    """
    try:
        # db = DBConn()
        # result = db.run_similar_serch(query)
        # return result if result else "No similar content found"
        return "Database functionality is currently disabled. Please uncomment the DBConn import to enable."
    except Exception as e:
        return f"Error searching database: {str(e)}"

@mcp.tool()
def load_pdf_to_database(pdf_path: str) -> str:
    """Load a PDF file into the database for similarity search.
    
    Args:
        pdf_path: Path to the PDF file to load
        
    Returns:
        Success message or error message
    """
    try:
        # db = DBConn()
        # db.load_data_from_pdf_path(pdf_path)
        # return f"Successfully loaded PDF: {pdf_path}"
        return "Database functionality is currently disabled. Please uncomment the DBConn import to enable."
    except Exception as e:
        return f"Error loading PDF: {str(e)}"

@mcp.tool()
def load_text_to_database(txt_path: str) -> str:
    """Load a text file into the database for similarity search.
    
    Args:
        txt_path: Path to the text file to load
        
    Returns:
        Success message or error message
    """
    try:
        # db = DBConn()
        # db.load_data_from_txt_path(txt_path)
        # return f"Successfully loaded text file: {txt_path}"
        return "Database functionality is currently disabled. Please uncomment the DBConn import to enable."
    except Exception as e:
        return f"Error loading text file: {str(e)}"




@mcp.tool()
def read_python_manual(topic: str = None) -> str:
    """Read Python documentation/manual for a specific topic or module.
    
    Args:
        topic: The Python module, function, or topic to get documentation for.
               If None, returns general Python help information.
               Examples: 'os', 'sys.path', 'list.append', 'str.split', 'MODULES'
        
    Returns:
        The Python documentation for the specified topic or error message
    """
    try:
        import pydoc
        from io import StringIO
        import sys
        
        # Capture the output from pydoc
        old_stdout = sys.stdout
        stdout_capture = StringIO()
        
        try:
            sys.stdout = stdout_capture
            
            if topic is None:
                # Show general help
                help()
            elif topic.upper() == 'MODULES':
                # List available modules
                pydoc.help('modules')
            else:
                # Get help for specific topic
                pydoc.help(topic)
            
            sys.stdout = old_stdout
            output = stdout_capture.getvalue()
            
            if not output.strip():
                return f"No documentation found for '{topic}'. Try using 'MODULES' to see available modules."
            
            # Limit output size to prevent overwhelming responses
            if len(output) > 10000:
                output = output[:10000] + "\n\n... [Documentation truncated for readability]"
            
            return output
            
        except Exception as inner_e:
            sys.stdout = old_stdout
            
            # Try alternative approach using __doc__ attribute
            try:
                if topic and '.' in topic:
                    # Handle dotted names like 'os.path'
                    module_parts = topic.split('.')
                    obj = __import__(module_parts[0])
                    for part in module_parts[1:]:
                        obj = getattr(obj, part)
                else:
                    # Simple module or builtin
                    try:
                        obj = __import__(topic) if topic else None
                    except ImportError:
                        obj = eval(topic) if topic else None
                
                if obj and hasattr(obj, '__doc__') and obj.__doc__:
                    doc = obj.__doc__
                    if len(doc) > 5000:
                        doc = doc[:5000] + "\n\n... [Documentation truncated]"
                    return f"Documentation for '{topic}':\n\n{doc}"
                else:
                    return f"No documentation available for '{topic}'"
                    
            except Exception as fallback_e:
                return f"Error accessing documentation for '{topic}': {str(inner_e)}\nFallback error: {str(fallback_e)}"
                
    except Exception as e:
        return f"Error reading Python manual: {str(e)}"

@mcp.tool()
def crawl_website(url: str, max_pages: int = 10, max_depth: int = 2, 
                 follow_external: bool = False, respect_robots: bool = True,
                 delay: float = 1.0, content_types: List[str] = None) -> str:
    """Crawl a website and extract structured data from multiple pages.
    
    Args:
        url: Starting URL to crawl
        max_pages: Maximum number of pages to crawl (default: 10)
        max_depth: Maximum depth to crawl from starting URL (default: 2)
        follow_external: Whether to follow external links (default: False)
        respect_robots: Whether to respect robots.txt (default: True)
        delay: Delay between requests in seconds (default: 1.0)
        content_types: List of content types to crawl (default: ['text/html'])
        
    Returns:
        JSON string containing crawled data and statistics
    """
    try:
        # Import required libraries with automatic installation
        installation_log = []
        required_packages = ['requests', 'beautifulsoup4', 'lxml']
        
        for package in required_packages:
            try:
                if package == 'beautifulsoup4':
                    from bs4 import BeautifulSoup
                elif package == 'requests':
                    import requests
                elif package == 'lxml':
                    import lxml
            except ImportError:
                installation_log.append(f"Installing {package}...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    installation_log.append(f"✓ Successfully installed {package}")
                else:
                    return f"Failed to install required package {package}: {result.stderr}"
        
        # Import after potential installation
        import requests
        from bs4 import BeautifulSoup
        
        if content_types is None:
            content_types = ['text/html']
        
        # Initialize crawler state
        visited_urls: Set[str] = set()
        to_visit: List[tuple] = [(url, 0)]  # (url, depth)
        crawled_data = []
        base_domain = urlparse(url).netloc
        
        # Check robots.txt if requested
        robots_parser = None
        if respect_robots:
            try:
                robots_parser = RobotFileParser()
                robots_url = urljoin(url, '/robots.txt')
                robots_parser.set_url(robots_url)
                robots_parser.read()
            except:
                robots_parser = None
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'RIGEL-Web-Crawler/1.0 (Educational/Research Tool)'
        })
        
        pages_crawled = 0
        
        while to_visit and pages_crawled < max_pages:
            current_url, depth = to_visit.pop(0)
            
            if current_url in visited_urls or depth > max_depth:
                continue
                
            # Check robots.txt
            if robots_parser and not robots_parser.can_fetch('*', current_url):
                continue
            
            try:
                # Add delay between requests
                if pages_crawled > 0:
                    time.sleep(delay)
                
                response = session.get(current_url, timeout=10)
                response.raise_for_status()
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if not any(ct in content_type for ct in content_types):
                    continue
                
                visited_urls.add(current_url)
                pages_crawled += 1
                
                # Parse HTML content
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract page data
                page_data = {
                    'url': current_url,
                    'title': soup.title.string.strip() if soup.title else 'No title',
                    'depth': depth,
                    'status_code': response.status_code,
                    'content_type': content_type,
                    'size_bytes': len(response.content),
                    'meta_description': '',
                    'meta_keywords': '',
                    'headers': [],
                    'links': [],
                    'images': [],
                    'text_content': '',
                    'structured_data': {}
                }
                
                # Extract meta information
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    page_data['meta_description'] = meta_desc.get('content', '')
                
                meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
                if meta_keywords:
                    page_data['meta_keywords'] = meta_keywords.get('content', '')
                
                # Extract headers
                for i in range(1, 7):
                    headers = soup.find_all(f'h{i}')
                    for header in headers:
                        page_data['headers'].append({
                            'level': i,
                            'text': header.get_text().strip()
                        })
                
                # Extract links and add to crawl queue
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    absolute_url = urljoin(current_url, href)
                    link_domain = urlparse(absolute_url).netloc
                    
                    page_data['links'].append({
                        'text': link.get_text().strip(),
                        'url': absolute_url,
                        'is_external': link_domain != base_domain
                    })
                    
                    # Add to crawl queue if conditions are met
                    if (absolute_url not in visited_urls and 
                        depth < max_depth and
                        (follow_external or link_domain == base_domain)):
                        to_visit.append((absolute_url, depth + 1))
                
                # Extract images
                for img in soup.find_all('img'):
                    src = img.get('src')
                    if src:
                        absolute_src = urljoin(current_url, src)
                        page_data['images'].append({
                            'src': absolute_src,
                            'alt': img.get('alt', ''),
                            'title': img.get('title', '')
                        })
                
                # Extract text content
                for script in soup(['script', 'style']):
                    script.decompose()
                page_data['text_content'] = soup.get_text()[:2000]  # Limit text content
                
                # Extract structured data (JSON-LD, microdata, etc.)
                json_ld_scripts = soup.find_all('script', type='application/ld+json')
                for script in json_ld_scripts:
                    try:
                        structured_data = json.loads(script.string)
                        page_data['structured_data']['json_ld'] = structured_data
                    except:
                        pass
                
                crawled_data.append(page_data)
                
            except Exception as e:
                # Log error but continue crawling
                error_data = {
                    'url': current_url,
                    'error': str(e),
                    'depth': depth,
                    'status': 'error'
                }
                crawled_data.append(error_data)
        
        # Compile final results
        result = {
            'crawl_summary': {
                'start_url': url,
                'pages_crawled': pages_crawled,
                'pages_found': len(visited_urls),
                'max_depth_reached': max([item.get('depth', 0) for item in crawled_data]),
                'domains_encountered': list(set([urlparse(item.get('url', '')).netloc 
                                               for item in crawled_data if 'url' in item])),
                'content_types_found': list(set([item.get('content_type', '') 
                                               for item in crawled_data if 'content_type' in item])),
                'total_size_bytes': sum([item.get('size_bytes', 0) for item in crawled_data]),
                'installation_log': installation_log
            },
            'pages': crawled_data
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return f"Error during web crawling: {str(e)}"

@mcp.tool()
def parse_webpage(url: str, extract_links: bool = True, extract_images: bool = True,
                 extract_text: bool = True, extract_metadata: bool = True,
                 extract_structured_data: bool = True, custom_selectors: Dict[str, str] = None) -> str:
    """Parse a single webpage and extract detailed information.
    
    Args:
        url: URL of the webpage to parse
        extract_links: Whether to extract all links (default: True)
        extract_images: Whether to extract image information (default: True)
        extract_text: Whether to extract text content (default: True)
        extract_metadata: Whether to extract meta tags (default: True)
        extract_structured_data: Whether to extract JSON-LD and microdata (default: True)
        custom_selectors: Dict of custom CSS selectors to extract specific elements
        
    Returns:
        JSON string containing parsed webpage data
    """
    try:
        # Import required libraries with automatic installation
        installation_log = []
        required_packages = ['requests', 'beautifulsoup4', 'lxml']
        
        for package in required_packages:
            try:
                if package == 'beautifulsoup4':
                    from bs4 import BeautifulSoup
                elif package == 'requests':
                    import requests
                elif package == 'lxml':
                    import lxml
            except ImportError:
                installation_log.append(f"Installing {package}...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    installation_log.append(f"✓ Successfully installed {package}")
                else:
                    return f"Failed to install required package {package}: {result.stderr}"
        
        # Import after potential installation
        import requests
        from bs4 import BeautifulSoup
        
        # Fetch the webpage
        headers = {
            'User-Agent': 'RIGEL-Web-Parser/1.0 (Educational/Research Tool)'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Initialize result structure
        result = {
            'url': url,
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'size_bytes': len(response.content),
            'encoding': response.encoding,
            'installation_log': installation_log
        }
        
        # Basic page information
        result['title'] = soup.title.string.strip() if soup.title else ''
        result['lang'] = soup.html.get('lang', '') if soup.html else ''
        
        # Extract metadata
        if extract_metadata:
            result['metadata'] = {}
            
            # Meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                name = meta.get('name') or meta.get('property') or meta.get('http-equiv')
                content = meta.get('content')
                if name and content:
                    result['metadata'][name] = content
            
            # Open Graph tags
            og_tags = soup.find_all('meta', property=lambda x: x and x.startswith('og:'))
            result['metadata']['open_graph'] = {}
            for og in og_tags:
                prop = og.get('property', '').replace('og:', '')
                content = og.get('content', '')
                if prop and content:
                    result['metadata']['open_graph'][prop] = content
            
            # Twitter Card tags
            twitter_tags = soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')})
            result['metadata']['twitter'] = {}
            for twitter in twitter_tags:
                name = twitter.get('name', '').replace('twitter:', '')
                content = twitter.get('content', '')
                if name and content:
                    result['metadata']['twitter'][name] = content
        
        # Extract links
        if extract_links:
            result['links'] = []
            for link in soup.find_all('a', href=True):
                absolute_url = urljoin(url, link['href'])
                result['links'].append({
                    'text': link.get_text().strip(),
                    'href': absolute_url,
                    'title': link.get('title', ''),
                    'target': link.get('target', ''),
                    'rel': link.get('rel', [])
                })
        
        # Extract images
        if extract_images:
            result['images'] = []
            for img in soup.find_all('img'):
                src = img.get('src')
                if src:
                    absolute_src = urljoin(url, src)
                    result['images'].append({
                        'src': absolute_src,
                        'alt': img.get('alt', ''),
                        'title': img.get('title', ''),
                        'width': img.get('width', ''),
                        'height': img.get('height', ''),
                        'loading': img.get('loading', '')
                    })
        
        # Extract text content
        if extract_text:
            # Remove script and style elements
            for script in soup(['script', 'style', 'nav', 'footer']):
                script.decompose()
            
            result['text_content'] = {
                'full_text': soup.get_text(),
                'paragraphs': [p.get_text().strip() for p in soup.find_all('p') if p.get_text().strip()],
                'headings': []
            }
            
            # Extract headings with hierarchy
            for i in range(1, 7):
                headings = soup.find_all(f'h{i}')
                for heading in headings:
                    result['text_content']['headings'].append({
                        'level': i,
                        'text': heading.get_text().strip(),
                        'id': heading.get('id', '')
                    })
        
        # Extract structured data
        if extract_structured_data:
            result['structured_data'] = {}
            
            # JSON-LD
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            result['structured_data']['json_ld'] = []
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    result['structured_data']['json_ld'].append(data)
                except:
                    pass
            
            # Microdata
            microdata_items = soup.find_all(attrs={'itemscope': True})
            result['structured_data']['microdata'] = []
            for item in microdata_items:
                microdata_obj = {
                    'type': item.get('itemtype', ''),
                    'properties': {}
                }
                
                props = item.find_all(attrs={'itemprop': True})
                for prop in props:
                    prop_name = prop.get('itemprop')
                    prop_value = prop.get('content') or prop.get_text().strip()
                    microdata_obj['properties'][prop_name] = prop_value
                
                result['structured_data']['microdata'].append(microdata_obj)
        
        # Custom selectors
        if custom_selectors:
            result['custom_extracts'] = {}
            for name, selector in custom_selectors.items():
                try:
                    elements = soup.select(selector)
                    result['custom_extracts'][name] = [
                        {
                            'text': elem.get_text().strip(),
                            'html': str(elem),
                            'attributes': dict(elem.attrs)
                        } for elem in elements
                    ]
                except Exception as e:
                    result['custom_extracts'][name] = f"Error with selector '{selector}': {str(e)}"
        
        # Additional technical information
        result['technical_info'] = {
            'doctype': str(soup.contents[0]) if soup.contents and hasattr(soup.contents[0], 'name') else '',
            'has_viewport_meta': bool(soup.find('meta', attrs={'name': 'viewport'})),
            'has_charset_meta': bool(soup.find('meta', attrs={'charset': True})),
            'external_scripts': [script.get('src') for script in soup.find_all('script', src=True)],
            'external_stylesheets': [link.get('href') for link in soup.find_all('link', rel='stylesheet', href=True)],
            'forms': [
                {
                    'action': form.get('action', ''),
                    'method': form.get('method', 'GET'),
                    'inputs': [
                        {
                            'type': inp.get('type', 'text'),
                            'name': inp.get('name', ''),
                            'id': inp.get('id', '')
                        } for inp in form.find_all('input')
                    ]
                } for form in soup.find_all('form')
            ]
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return f"Error parsing webpage: {str(e)}"

@mcp.tool()
def extract_text_from_url(url: str, selector: str = None, clean: bool = True) -> str:
    """Extract clean text content from a URL, optionally using CSS selectors.
    
    Args:
        url: URL to extract text from
        selector: Optional CSS selector to target specific elements
        clean: Whether to clean and format the text (default: True)
        
    Returns:
        Extracted text content or error message
    """
    try:
        # Import required libraries
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            # Install required packages
            packages = ['requests', 'beautifulsoup4']
            for package in packages:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode != 0:
                    return f"Failed to install {package}: {result.stderr}"
            
            import requests
            from bs4 import BeautifulSoup
        
        # Fetch the page
        headers = {
            'User-Agent': 'RIGEL-Text-Extractor/1.0 (Educational/Research Tool)'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Select specific elements if selector provided
        if selector:
            elements = soup.select(selector)
            if not elements:
                return f"No elements found for selector: {selector}"
            text_content = ' '.join([elem.get_text() for elem in elements])
        else:
            # Remove unwanted elements
            for unwanted in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                unwanted.decompose()
            text_content = soup.get_text()
        
        if clean:
            # Clean up the text
            lines = text_content.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line and len(line) > 1:  # Skip empty lines and single characters
                    cleaned_lines.append(line)
            
            text_content = '\n'.join(cleaned_lines)
            
            # Remove excessive whitespace
            text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
            text_content = re.sub(r' +', ' ', text_content)
        
        return text_content
        
    except Exception as e:
        return f"Error extracting text from URL: {str(e)}"

@mcp.tool()
def check_file_sizes(directory_path: str = ".", include_hidden: bool = False, 
                    sort_by: str = "size", human_readable: bool = True) -> str:
    """Check file sizes in a given directory with detailed information.
    
    Args:
        directory_path: Path to the directory to analyze (defaults to current directory)
        include_hidden: Whether to include hidden files (starting with .) (default: False)
        sort_by: How to sort results - 'size', 'name', 'modified' (default: 'size')
        human_readable: Whether to show sizes in human readable format (KB, MB, GB) (default: True)
        
    Returns:
        Formatted string with file sizes and directory statistics
    """
    try:
        import os
        import stat
        from datetime import datetime
        
        if not os.path.exists(directory_path):
            return f"Error: Directory '{directory_path}' does not exist"
        
        if not os.path.isdir(directory_path):
            return f"Error: '{directory_path}' is not a directory"
        
        def format_size(size_bytes):
            """Convert bytes to human readable format."""
            if not human_readable:
                return str(size_bytes)
            
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.1f} PB"
        
        def get_file_info(file_path):
            """Get file information including size and modification time."""
            try:
                stat_info = os.stat(file_path)
                return {
                    'name': os.path.basename(file_path),
                    'full_path': file_path,
                    'size': stat_info.st_size,
                    'modified': stat_info.st_mtime,
                    'is_dir': stat.S_ISDIR(stat_info.st_mode),
                    'permissions': stat.filemode(stat_info.st_mode)
                }
            except (OSError, IOError) as e:
                return {
                    'name': os.path.basename(file_path),
                    'full_path': file_path,
                    'size': 0,
                    'modified': 0,
                    'is_dir': False,
                    'permissions': 'unknown',
                    'error': str(e)
                }
        
        # Get all items in directory
        items = []
        total_size = 0
        file_count = 0
        dir_count = 0
        
        try:
            for item_name in os.listdir(directory_path):
                # Skip hidden files if not requested
                if not include_hidden and item_name.startswith('.'):
                    continue
                
                item_path = os.path.join(directory_path, item_name)
                file_info = get_file_info(item_path)
                items.append(file_info)
                
                if file_info['is_dir']:
                    dir_count += 1
                else:
                    file_count += 1
                    total_size += file_info['size']
        
        except PermissionError:
            return f"Error: Permission denied accessing directory '{directory_path}'"
        
        # Sort items
        if sort_by == "size":
            items.sort(key=lambda x: x['size'], reverse=True)
        elif sort_by == "name":
            items.sort(key=lambda x: x['name'].lower())
        elif sort_by == "modified":
            items.sort(key=lambda x: x['modified'], reverse=True)
        else:
            return f"Error: Invalid sort_by option '{sort_by}'. Use 'size', 'name', or 'modified'"
        
        # Format output
        abs_directory_path = os.path.abspath(directory_path)
        result = [f"File sizes in directory: {abs_directory_path}"]
        result.append("=" * 80)
        
        # Summary statistics
        result.append(f"Summary:")
        result.append(f"  Total files: {file_count}")
        result.append(f"  Total directories: {dir_count}")
        result.append(f"  Total size (files only): {format_size(total_size)}")
        result.append(f"  Sorted by: {sort_by}")
        result.append(f"  Hidden files included: {include_hidden}")
        result.append("")
        
        # Header
        if human_readable:
            result.append(f"{'Type':<4} {'Permissions':<11} {'Size':<10} {'Modified':<19} {'Name'}")
        else:
            result.append(f"{'Type':<4} {'Permissions':<11} {'Size (bytes)':<15} {'Modified':<19} {'Name'}")
        result.append("-" * 80)
        
        # File listings
        for item in items:
            type_indicator = "DIR" if item['is_dir'] else "FILE"
            
            if 'error' in item:
                size_str = f"ERROR: {item['error']}"
                modified_str = "unknown"
            else:
                size_str = format_size(item['size']) if not item['is_dir'] else "-"
                modified_str = datetime.fromtimestamp(item['modified']).strftime("%Y-%m-%d %H:%M:%S")
            
            permissions = item['permissions']
            name = item['name']
            
            # Truncate long names
            if len(name) > 40:
                name = name[:37] + "..."
            
            if human_readable:
                result.append(f"{type_indicator:<4} {permissions:<11} {size_str:<10} {modified_str:<19} {name}")
            else:
                size_display = str(item['size']) if not item['is_dir'] else "-"
                result.append(f"{type_indicator:<4} {permissions:<11} {size_display:<15} {modified_str:<19} {name}")
        
        # Additional statistics for largest files
        if file_count > 0:
            result.append("")
            result.append("Largest files:")
            file_items = [item for item in items if not item['is_dir'] and 'error' not in item]
            file_items.sort(key=lambda x: x['size'], reverse=True)
            
            for i, item in enumerate(file_items[:5]):  # Top 5 largest files
                percentage = (item['size'] / total_size * 100) if total_size > 0 else 0
                result.append(f"  {i+1}. {item['name']}: {format_size(item['size'])} ({percentage:.1f}%)")
        
        return "\n".join(result)
        
    except Exception as e:
        return f"Error checking file sizes: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="sse")
