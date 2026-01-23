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

# HELLO WORLD

__RIGEL = """
RIGEL V4.0 - Main Source
                                                                              :::::   :::::
                                                                        ::                     ::
                                                                     :                             :
                                                                  :                                   :
                                                               :                                         :
                                                             :                                             :
                                                           :                                                 :
                                                           :                                                 :

                                                                         ::::               ::::
                                                            :       ::                             ::       :
                                                                :                                       :
                                                            ::                                             ::
                                                         ::  :                                             :  ::
                                                       :     :                                             :     :
                                                    :               :::::::::                   :::                 :
                                                  :           :::::::    :::::::::::::::::::::         ::::           :
                                                :         ::  :::  :::::::::::::::::   :::::::::::::::    :  ::         :
                                                      ::    ::::::::::                             :::::::::     ::
                                            :      :     :::::::                    ::::                 :::: ::     ::     :
                                          :    ::    :: ::::   :       ::::            ::      :::       :   ::   ::     :    :
                                         :  :     :   :::       : ::                      :          :: :        ::   :     :  :
                                         ::    :   :  :       :::                           :           :::          :   :    ::
                                       :  : :   :    :    :     :                             :         :     :         :   : :  :
                                    :    :::  :     :  :                                                         :         : :::    :
                                  :    :   ::      ::            :                                     :            :       ::   :    :
                                     :   :  :    ::                                                                   :     :      :
                             :    :   :        :::                              :::::::::            ::                  :        :   :    :
                           :    :   :        :: :                 :         :::::       :::::         ::                  ::        :   :    :
                         :    :   :        :  ::                         ::::               ::::         :                :  :        :   :    :
                       :   ::   :        :    ::                   :   :::                     :::   :     :                   :        :   :    :
                     :        :        :                           :::::                         :: ::       :                   :        :        :
                            ::       :          :                  ::                               :::        :        :          :       ::
                  :           :    :             :                  :                               :                  :             :    :
                :        :     :           :                   :         :::                 :::                  :                    : :              :
              :        :        :         :                  :    : :::                            :: :    :        ::                  :        :        :
                     :        :                             :   ::                                     ::            ::                   :        :
           :        :                               :     :   ::      :                           :      :::  :     :                                        :
         :        :        :            :            :   : :                                                 :::   :                         :        :        :
        :                            :                 ::                                                       ::         :       :                            :
      :        :        :             ::              ::                :                       :                ::          :    :             :        :        :
                                      :             ::                                                             ::
   :        :        :                   :        : :      :             :                     :             :      : :        ::                  :        :        :
  :        :                         :          :  :      :                                                   :      :  :         :                          :        :
:        :        :                 :       : :   :       :                                                   :       :   : :      :
 :        :        :                        ::                                       0                                     ::                        :        :        :
                                       :   :   :                                            :                            :   :   :
    :        :        :                  :             :                     :             :                     :             :                           :        :
                       :                          :   :        :                          :              :        :   :                          :
       :        :                     :     :       :: :        :               :       :               :        : ::       :     :                     :        :
                          :          :        :      :: :                         :   :                           ::      :                   :
          :        :        :                           :::        :                                 :         ::                                    :        :
            :                :    :              :        ::         :                             :         ::        :              :    :                :
                      :        :                   :        ::                                             ::        :                   :        :        :
               :        :       :                    :        :::                                       :::        :                    :       :        :
                 :            :   :               :    :        :  :       :                 :       :  :        :    :               :   :            :
                           : :      :                ::::             ::       ::       ::       ::             : ::                :      : :
                    :       ::        :                  :::                :::  :::::::  ::::               :::                  :        ::       :
                      :    :: ::        :                   ::::      :                           :      ::::                   :        :: :     :
                        :      :::        :                   :     :::::::                   :::::::     :                   :        :::      :
                          :       :::       :                   :         :::::::::::::::::::::         :                   :       :::       :
                            :       :::       :                   :               :::::               :                   :       :::       :
                                       :::       :                                                                      :      :::        :
                                 :       ::::      :                                                                 :      ::::       :
                                   :        :::::     :                :                                          :     :::::        :
                                     ::        :   ::   ::               :                     :               ::   ::   :         :
                                        :         :     ::::::             :                 :             ::::::     :         :
                                           :         :       ::::::          :             :          ::::::       :         :
                                              :         ::         :::::::::  :::       :::  ::::::::::        ::         :
                                                 :          ::            :::::::::::::::::::::            ::          :
                                                    ::           ::                :::                ::           ::
                                                        ::             :::                     :::             ::
                                                             ::                                           ::
                                                                  :::                               :::
                                                                           ::::::::: :::::::::
"""
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from core.logger import SysLog
import os
import glob
import getpass
import subprocess
import base64
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from mcp import ClientSession, StdioServerParameters
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.client.stdio import stdio_client
from langgraph.prebuilt import create_react_agent
import re
from langchain.chains import ConversationChain
import random
from langchain_mcp_adapters.client import MultiServerMCPClient
import os
from core.rdb import DBConn
from typing import Dict, List, Any, Optional, Union, Tuple
import httpx

# Import OSTools if available
try:
    from core.os_tools import OSTools
    OS_TOOLS_AVAILABLE = True
except ImportError:
    OS_TOOLS_AVAILABLE = False


syslog = SysLog(name="RigelEngine", level="DEBUG", log_file="rigel.log")
hello_string = "Zerone Laboratories Systems - RIGEL Engine v4.0[Alpha]\n"

# Configure MCP tools endpoint via environment variable, fallback to localhost
_TOOLS_SSE_URL = os.environ.get("RIGEL_MCP_TOOLS_SSE_URL", "http://localhost:8001/sse")
default_mcp = MultiServerMCPClient(
    {
        "rigel tools": {
            "url": _TOOLS_SSE_URL,
            "transport": "sse",
        }
    },
)

class Rigel: # RIGEL Super Class. Use this to create derived classes
    def __init__(self, model_name: str = "llama3.2", chatmode: str = "ollama", mcp_endpoint = default_mcp, temp=0.7):
        self.model = model_name
        self.chatmode = chatmode
        self.llm = None
        self.messages = None
        self.chain = None
        self.thought_prompt = None
        self.workflow = StateGraph(state_schema=MessagesState)
        self.memory = None
        self.app = None
        self.temp = temp
        self.agent = None
        self.client = None
        self.ragdb = None
        self._initialized = False
        self.server_params = StdioServerParameters(
            command="python",
            args=["/home/zerone/Projects/RIGEL_SERVICE/core/mcp/rigel_tools_server.py"],
        )
        self.continuity = """
                        Proceed. You CAN run code on my machine.
                        ALWAYS run  the command in the 'Working Directory' and remember the working directory
                        When providing tool outputs (like file listings, command results, etc.), always include the actual output in your response.
                        If the entire task I asked for is done, say exactly 'The task is done.' after providing all relevant outputs and results.
                        If you need some specific information (like username or password) say EXACTLY 'Please provide more information.'
                        If it's impossible, say 'The task is impossible.'
                        (If I haven't provided a task, say exactly 'Let me know what you'd like to do next.') Otherwise keep going.
        """

        self.think_n_plan = """
        Analyse and try to find the best and optimum way to do a specific problem that the user requested. If the thinking process is done,
        Say exactly 'Task is done'. If its impossible exactly say 'Task is impossible'.
        """

        self.continuity_breakers = [
            r"The task is done\.",
            r"Please provide more information\.",
            r"The task is impossible\.",
            r"Let me know what you'd like to do next\.",
            r"Let me know\."
        ]
        self.continuity_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.continuity_breakers]
        # runtime memory adapter
        # self.memory = ConversationBufferMemory(memory_key="history", return_messages=True)

        # self.conversation = ConversationChain(
        #     llm=self.llm,
        #     memory=self.memory,
        #     prompt=self.prompt,
        #     verbose=False
        # )
        self.client = mcp_endpoint
        
        # Initialize OS Tools if available
        if OS_TOOLS_AVAILABLE:
            self.os_tools = OSTools()
            syslog.info("OS Tools initialized successfully")
        else:
            self.os_tools = None
            syslog.warning("OS Tools module not available. Advanced OS operations will be limited.")

    def readAndInitializeDatabase(self):
        # Check if the database already exists and is populated
        db_path = "db/chroma_db"
        if os.path.exists(db_path) and os.path.isdir(db_path):
            # Check if files exist in the chroma DB directory that indicate it's already initialized
            chroma_files = glob.glob(os.path.join(db_path, "chroma.sqlite3"))
            if chroma_files:
                syslog.info("ChromaDB is already initialized, reusing existing database")
                self.ragdb = DBConn()
                return
        
        # If we get here, we need to initialize the database
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rigel_data_dir = os.path.join(current_dir, "rigel_data")
        pdf_pattern = os.path.join(rigel_data_dir, "*.pdf")
        pdf_files = glob.glob(pdf_pattern)

        if not pdf_files:
            syslog.warning(f"No PDF files found in {rigel_data_dir}")
            return

        self.ragdb = DBConn()
        for pdf_file in pdf_files:
            try:
                self.ragdb.load_data_from_pdf_path(pdf_file)
                syslog.info(f"Loaded PDF file: {os.path.basename(pdf_file)}")
            except Exception as e:
                syslog.error(f"Error loading PDF file {pdf_file}: {str(e)}")

        syslog.info(f"Database Successfully Initialized with {len(pdf_files)} PDF files!")




    def inference(self, messages: list, model: str = None, RAG: bool = False):
        self.messages = messages
        """
        Input should be in following format:
        [
            (
                "system",
                "SystemPrompt goes here",
            ),
            (   "human", "{input}"
            ),
        ]
        """

        self.prompt = ChatPromptTemplate.from_messages(self.messages)
        self.chain = self.prompt | self.llm
        syslog.debug(self.chain)
        response = self.chain.invoke({})
        syslog.info(response)
        return AIMessage(content=response.content)

    async def __init_mcp(self):
        if not self._initialized:
            try:
                self.tools = await self.client.get_tools()
                self.agent = create_react_agent(self.llm, self.tools)
                self._initialized = True
            except Exception as e:
                print(f"Failed to initialize MCP client: {e}")
                raise e
    async def cleanup_mcp(self):
        try:
            self.agent = None
            self.tools = None
            self._initialized = False
            syslog.info("MCP resources cleaned up successfully.")
        except Exception as e:
            syslog.warning(f"Error during MCP cleanup: {e}")


    async def inference_with_tools(self, prompt, tools=None):
        if not self._initialized:
            try:
                await self.__init_mcp()
            except Exception as e:
                syslog.error(f"Failed to initialize MCP client: {e}")
                hint = (
                    f"Tools unavailable. Could not connect to MCP tools server at {_TOOLS_SSE_URL}.\n"
                    "Start the built-in server with: python core/mcp/rigel_tools_server.py\n"
                    "Or set RIGEL_MCP_TOOLS_SSE_URL to your tools server SSE endpoint."
                )
                return AIMessage(content=f"Error occurred during tool-based inference: {str(e)}\n\n{hint}")

        messages = [
            SystemMessage(content=self.continuity),
            {"role": "user", "content": prompt}
        ]

        max_iterations = 10
        iteration_count = 0
        
        full_process_log = [] 

        try:
            while iteration_count < max_iterations:
                iteration_count += 1
                syslog.info(f"Inference iteration {iteration_count}")
                
                result = None
                for attempt in range(2):
                    try:
                        result = await self.agent.ainvoke({"messages": messages})
                        break
                    except Exception as e:
                        syslog.error(f"Inference Attempt {attempt+1} Failed: {str(e)}")
                        if attempt == 1: # Last attempt failed
                            error_msg = f"[System Error]: Agent invocation failed after retries: {str(e)}"
                            full_process_log.append(error_msg)
                            return AIMessage(content="\n\n".join(full_process_log))

                current_total_messages = result["messages"]
                new_messages_count = len(current_total_messages) - len(messages)
                new_messages = current_total_messages[-new_messages_count:]

                iteration_buffer = []

                for msg in new_messages:
                    if hasattr(msg, 'content') and msg.content:
                        content_str = str(msg.content)
                        iteration_buffer.append(content_str)
                    
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            name = tool_call.get('name', 'unknown')
                            args = tool_call.get('args', {})
                            log_entry = f"🛠️ [Tool Call - {name}]: {args}"
                            iteration_buffer.append(log_entry)

                    if msg.type == 'tool' or msg.type == 'function':
                        if not (hasattr(msg, 'content') and msg.content):
                            log_entry = f"[Tool Result]: {str(msg)}"
                            iteration_buffer.append(log_entry)

                full_process_log.extend(iteration_buffer)
                messages = current_total_messages
                final_message = messages[-1]
                syslog.info(f"Iteration {iteration_count} complete. Last msg type: {type(final_message)}")
                if hasattr(final_message, 'content') and final_message.content:
                    response_content = final_message.content
                    
                    continuity_breaker_found = False
                    for pattern in self.continuity_patterns:
                        if pattern.search(response_content):
                            syslog.info("Continuity breaker detected. Task Complete.")
                            continuity_breaker_found = True
                            break

                    if continuity_breaker_found:
                        return AIMessage(content="\n\n".join(full_process_log))

                    syslog.info(f"No continuity breaker. Continuing execution (Iteration {iteration_count})")
                    
                    messages.append({"role": "user", "content": "Continue with the task."})
                else:
                    pass

            syslog.warning(f"Reached maximum iterations ({max_iterations}) without continuity breaker")
            timeout_msg = f"\n\n[System]: Task execution reached maximum iterations ({max_iterations}) without explicit completion."
            full_process_log.append(timeout_msg)
            
            return AIMessage(content="\n\n".join(full_process_log))

        except Exception as e:
            syslog.error(f"Critical error in inference_with_tools: {e}")
            error_msg = f"\n\n[System Critical Error]: {str(e)}"
            full_process_log.append(error_msg)
            return AIMessage(content="\n\n".join(full_process_log))
            
        finally:
            syslog.info("Cleaning Up MCP")
            await self.cleanup_mcp()

    def inference_with_memory(self, messages: list, model: str = None, thread_id: str = "default", RAG: bool = False):
        """
        use this function as follows

        Args:
            messages: List of messages in format [("role", "content"), ...]
            model: Optional model name override
            thread_id: Thread ID for conversation memory

        Returns:
            AIMessage with response content
        """
        system_message = ""

        syslog.info(f"RAG IS CURRENTLY {RAG}")
        if RAG:
            data = self.ragdb.run_similar_search(next((msg for role, msg in messages if role == "human"), ""))
            syslog.info(f"RAG Data Retrieved: {data}")
            messages.append(("RAG",f"{data}"))

        formatted_messages = []
        for role, content in messages:
            if role == "system":
                syslog.info(f"Adding system message: {content}")
                system_message  = content
                formatted_messages.append(SystemMessage(content=content))
            if role == "RAG":
                formatted_messages.append({"role": "user", "content": content})
            elif role == "human":
                formatted_messages.append({"role": "user", "content": content})
            elif role == "ai":
                formatted_messages.append({"role": "assistant", "content": content})

        if not self.app:
            self._setup_workflow(system_message)


        config = {"configurable": {"thread_id": thread_id}}
        response = self.app.invoke(
            {"messages": formatted_messages},
            config=config
        )
        last_message = response["messages"][-1]
        syslog.info(response)
        return AIMessage(content=last_message.content)

    def _setup_workflow(self, system):
        def call_model(state: MessagesState):
            system_prompt = system
            messages = [SystemMessage(content=system_prompt)] + state["messages"]
            response = self.llm.invoke(messages)
            return {"messages": response}
        self.workflow.add_node("model", call_model)
        self.workflow.add_edge(START, "model")

        # Checkpointer
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)


    def think(self, think_message, model: str = None):
        self.thought_prompt = f"""
        Think of the best way to do this and list it out in a short manner. nothing more or nothing less.
        If the thinking process is done, say exactly 'The task is done'. If it's impossible exactly say 'The task is impossible'.
        """
        self.prompt = [
            (
                "system",
                self.thought_prompt,
            ),
            (
                "human",
                think_message,
            ),
        ]
        max_iterations = 10
        iteration_count = 0
        while iteration_count < max_iterations:
            iteration_count += 1
            output = self.inference_with_memory(self.prompt, thread_id=f"THINK{random.random()}")
            if hasattr(output, 'content') and output.content:
                response_content = output.content

                continuity_breaker_found = False
                for pattern in self.continuity_patterns:
                    if pattern.search(response_content):
                        syslog.info(f"Think method: Continuity breaker detected: {response_content}")
                        continuity_breaker_found = True
                        break

                if continuity_breaker_found:
                    return response_content

                syslog.info(f"Think method: No continuity breaker detected. Continuing (iteration {iteration_count})")
                syslog.info(f"Current output {response_content}")

        syslog.warning(f"Think method: Reached maximum iterations ({max_iterations}) without continuity breaker")
        return response_content

    def decision(self, decision_message, model: str = None):
        "[TODO]"
        return 0

    def get_conversation_history(self, thread_id: str = "default"):
        """
        retrieve conversation

        Args:
            thread_id: Thread ID to get history for

        Returns:
            List of messages in the conversation
        """
        if not self.app:
            self._setup_workflow()

        config = {"configurable": {"thread_id": thread_id}}

        try:
            state = self.app.get_state(config)
            return state.values.get("messages", [])
        except Exception as e:
            syslog.warning(f"Could not retrieve conversation history: {e}")
            return []

    def clear_memory(self, thread_id: str = "default"):
        """
        clear memory

        Args:
            thread_id: Thread ID to clear
        """
        if not self.app or not self.memory:
            return

        config = {"configurable": {"thread_id": thread_id}}

        try:
            # This will clear the memory for the thread
            self.memory.delete(config)
            syslog.info(f"Cleared memory for thread: {thread_id}")
        except Exception as e:
            syslog.warning(f"Could not clear memory for thread {thread_id}: {e}")
            
    def execute_command(self, command: str, timeout: int = 30, 
                        working_dir: str = None) -> Dict[str, Any]:
        """
        Execute a system command safely with timeout and output capture.
        
        Args:
            command: The shell command to execute
            timeout: Command timeout in seconds (default: 30)
            working_dir: Directory to execute command in (defaults to current directory)
            
        Returns:
            Dictionary with command result and output
        """
        if not self.os_tools:
            syslog.error("OS Tools not available")
            return {"success": False, "error": "OS Tools not available"}
            
        return self.os_tools.execute_command(
            command=command,
            timeout=timeout,
            working_dir=working_dir
        )
    
    def create_temp_program(self, content: str, file_extension: str = ".py") -> Dict[str, Any]:
        """
        Create a temporary program file with the given content.
        
        Args:
            content: Source code to write to the file
            file_extension: File extension for the temporary file (defaults to .py)
            
        Returns:
            Dictionary with file information
        """
        if not self.os_tools:
            syslog.error("OS Tools not available")
            return {"success": False, "error": "OS Tools not available"}
            
        return self.os_tools.create_temp_program(
            content=content,
            file_extension=file_extension
        )
    
    def execute_temp_program(self, file_path: str, args: List[str] = None, 
                            interpreter: str = None, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute a temporary program with optional arguments and interpreter.
        
        Args:
            file_path: Path to the temporary program file
            args: List of command-line arguments to pass to the program
            interpreter: Interpreter to use (e.g., "python", "node", "bash")
                        If None, determined by file extension
            timeout: Execution timeout in seconds
            
        Returns:
            Dictionary with execution result
        """
        if not self.os_tools:
            syslog.error("OS Tools not available")
            return {"success": False, "error": "OS Tools not available"}
            
        return self.os_tools.execute_temp_program(
            file_path=file_path,
            args=args,
            interpreter=interpreter,
            timeout=timeout
        )
    
    def create_and_execute_program(self, content: str, file_extension: str = ".py", 
                                  args: List[str] = None, interpreter: str = None, 
                                  timeout: int = 30, cleanup: bool = True) -> Dict[str, Any]:
        """
        Create and execute a temporary program in one operation.
        
        Args:
            content: Source code content
            file_extension: File extension
            args: Program arguments
            interpreter: Program interpreter
            timeout: Execution timeout
            cleanup: Whether to delete the temporary file after execution
            
        Returns:
            Dictionary with execution result
        """
        if not self.os_tools:
            syslog.error("OS Tools not available")
            return {"success": False, "error": "OS Tools not available"}
            
        return self.os_tools.create_and_execute_program(
            content=content,
            file_extension=file_extension,
            args=args,
            interpreter=interpreter,
            timeout=timeout,
            cleanup=cleanup
        )
    
    def get_detailed_system_info(self) -> Dict[str, Any]:
        """
        Get detailed system information.
        
        Returns:
            Dictionary with extensive system information
        """
        if not self.os_tools:
            syslog.error("OS Tools not available")
            return {"success": False, "error": "OS Tools not available"}
            
        return self.os_tools.get_detailed_system_info()

    def visual_inference(self, prompt: str, image_source: Union[str, bytes, List[Union[str, bytes]]], 
                         model: str = None, detail: str = "auto") -> AIMessage:
        """
        Perform visual inference on image(s) with a text prompt.
        Supports vision-capable models for image understanding and analysis.
        
        Args:
            prompt: Text prompt/question about the image(s)
            image_source: Can be one of:
                - A file path to a local image (str)
                - A URL to an image (str starting with http:// or https://)
                - Raw image bytes (bytes)
                - A list of any combination of the above for multi-image analysis
            model: Optional model override (should be a vision-capable model)
                   For Ollama: llava, llava-llama3, bakllava, moondream, etc.
                   For Groq: llama-3.2-90b-vision-preview, llama-3.2-11b-vision-preview, etc.
            detail: Image detail level - "low", "high", or "auto" (default: "auto")
                   Only applicable for some providers
                   
        Returns:
            AIMessage with the model's response about the image(s)
            
        Example:
            # Single image from file
            response = rigel.visual_inference("What's in this image?", "/path/to/image.jpg")
            
            # Single image from URL
            response = rigel.visual_inference("Describe this", "https://example.com/image.png")
            
            # Multiple images
            response = rigel.visual_inference(
                "Compare these two images",
                ["/path/to/image1.jpg", "https://example.com/image2.png"]
            )
        """
        def _encode_image_to_base64(image_path: str) -> str:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        
        def _get_image_mime_type(image_path: str) -> str:
            ext = os.path.splitext(image_path)[1].lower()
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
            }
            return mime_types.get(ext, "image/jpeg")
        
        def _process_image_source(source: Union[str, bytes]) -> Dict[str, Any]:
            if isinstance(source, bytes):
                base64_image = base64.b64encode(source).decode("utf-8")
                return {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": detail
                    }
                }
            elif isinstance(source, str):
                if source.startswith(("http://", "https://")):
                    return {
                        "type": "image_url",
                        "image_url": {
                            "url": source,
                            "detail": detail
                        }
                    }
                else:
                    if not os.path.exists(source):
                        raise FileNotFoundError(f"Image file not found: {source}")
                    base64_image = _encode_image_to_base64(source)
                    mime_type = _get_image_mime_type(source)
                    return {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}",
                            "detail": detail
                        }
                    }
            else:
                raise ValueError(f"Unsupported image source type: {type(source)}")
        
        content = [{"type": "text", "text": prompt}]
        
        if isinstance(image_source, list):
            for source in image_source:
                content.append(_process_image_source(source))
        else:
            content.append(_process_image_source(image_source))
        
        message = HumanMessage(content=content)
        
        original_model = None
        if model:
            original_model = self.llm.model
            self.llm.model = model
        
        try:
            syslog.info(f"Performing visual inference with model: {self.llm.model}")
            response = self.llm.invoke([message])
            syslog.info(f"Visual inference completed successfully")
            return AIMessage(content=response.content)
        except Exception as e:
            syslog.error(f"Visual inference failed: {str(e)}")
            raise
        finally:
            if original_model:
                self.llm.model = original_model

    async def visual_inference_with_memory(self, prompt: str, image_source: Union[str, bytes, List[Union[str, bytes]]],
                                           thread_id: str = "default", model: str = None, 
                                           detail: str = "auto") -> AIMessage:
        """
        Perform visual inference with conversation memory support.
        
        Args:
            prompt: Text prompt/question about the image(s)
            image_source: Image file path, URL, bytes, or list of these
            thread_id: Thread ID for conversation memory
            model: Optional vision model override
            detail: Image detail level - "low", "high", or "auto"
            
        Returns:
            AIMessage with the model's response
        """
        def _encode_image_to_base64(image_path: str) -> str:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        
        def _get_image_mime_type(image_path: str) -> str:
            ext = os.path.splitext(image_path)[1].lower()
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
            }
            return mime_types.get(ext, "image/jpeg")
        
        def _process_image_source(source: Union[str, bytes]) -> Dict[str, Any]:
            if isinstance(source, bytes):
                base64_image = base64.b64encode(source).decode("utf-8")
                return {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": detail
                    }
                }
            elif isinstance(source, str):
                if source.startswith(("http://", "https://")):
                    return {
                        "type": "image_url",
                        "image_url": {
                            "url": source,
                            "detail": detail
                        }
                    }
                else:
                    if not os.path.exists(source):
                        raise FileNotFoundError(f"Image file not found: {source}")
                    base64_image = _encode_image_to_base64(source)
                    mime_type = _get_image_mime_type(source)
                    return {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}",
                            "detail": detail
                        }
                    }
            else:
                raise ValueError(f"Unsupported image source type: {type(source)}")
        
        content = [{"type": "text", "text": prompt}]
        
        if isinstance(image_source, list):
            for source in image_source:
                content.append(_process_image_source(source))
        else:
            content.append(_process_image_source(image_source))
        
        if not self.app:
            self._setup_workflow("You are RIGEL, a helpful AI assistant with vision capabilities.")
        
        original_model = None
        if model:
            original_model = self.llm.model
            self.llm.model = model
        
        try:
            config = {"configurable": {"thread_id": thread_id}}
            visual_message = HumanMessage(content=content)
            response = self.app.invoke(
                {"messages": [visual_message]},
                config=config
            )
            last_message = response["messages"][-1]
            syslog.info(f"Visual inference with memory completed for thread: {thread_id}")
            return AIMessage(content=last_message.content)
        except Exception as e:
            syslog.error(f"Visual inference with memory failed: {str(e)}")
            raise
        finally:
            if original_model:
                self.llm.model = original_model

class RigelOllama(Rigel): # RIGEL with ollama backend
    def __init__(self, model_name: str = "llama3.2",  mcp_endpoint = default_mcp, temp=0.7):
        super().__init__(model_name=model_name, chatmode="ollama", mcp_endpoint=mcp_endpoint)
        self.llm = ChatOllama(model=self.model, temperature=temp)

    def _pull_model(self, model_name: str):
        try:
            syslog.info(f"Model '{model_name}' not found. Attempting to pull it...")
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True,
                text=True,
                timeout=600
            )
            if result.returncode == 0:
                syslog.info(f"Successfully pulled model '{model_name}'")
                return True
            else:
                syslog.error(f"Failed to pull model '{model_name}': {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            syslog.error(f"Timeout while pulling model '{model_name}'")
            return False
        except Exception as e:
            syslog.error(f"Error pulling model '{model_name}': {str(e)}")
            return False

    def inference(self, messages: list, model: str = None):
        if model:
            self.llm.model = model
        
        try:
            return super().inference(messages)
        except Exception as e:
            error_str = str(e)
            if "not found" in error_str.lower() and "404" in error_str:
                model_to_use = model if model else self.model
                syslog.warning(f"Model '{model_to_use}' not found, attempting to pull...")
                
                if self._pull_model(model_to_use):
                    syslog.info(f"Model '{model_to_use}' pulled successfully, retrying inference...")
                    return super().inference(messages)
                else:
                    syslog.error(f"Failed to pull model '{model_to_use}', cannot proceed with inference")
                    raise
            else:
                raise

class RigelGroq(Rigel): # RIGEL with groq backend
    def __init__(self, model_name: str = "llama3-70b-8192", temp: float = 0.7,  mcp_endpoint = default_mcp):
        super().__init__(model_name=model_name, chatmode="groq", mcp_endpoint=mcp_endpoint)
        if "GROQ_API_KEY" not in os.environ:
            try:
                os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key: ")
            except Exception as e:
                syslog.error(f"Failed to get Groq API key: {e}")
                syslog.error("When running in Docker, make sure to set GROQ_API_KEY environment variable without quotes")
                raise RuntimeError("GROQ_API_KEY environment variable is not set and unable to prompt for input")
        
        try:
            self.llm = ChatGroq(model=self.model,
                                temperature=temp,
                                )
            syslog.info(f"Successfully initialized Groq LLM with model {self.model}")
        except Exception as e:
            syslog.error(f"Failed to initialize Groq LLM: {e}")
            syslog.error("Check that your GROQ_API_KEY is valid and properly set")
            raise

    def inference(self, messages: list, model: str = None):
        if model:
            self.llm.model = model
        return super().inference(messages)
    
class RigelAutoSwap(Rigel):
    def __init__(self, model_name: str = "llama-swap-model", base_url: str = "http://localhost:12432", temp: float = 0.7):
        super().__init__(model_name=model_name, chatmode="llama-swap")
        self.base_url = base_url
        self.llm = ChatOpenAI(
            model=self.model,
            base_url=f"{self.base_url}/v1",
            api_key="not-needed",
            temperature=temp,
        )
        syslog.info(f"Initialized RIGEL with llama.cpp server at {self.base_url}")


# Some Demos
if __name__ == "__main__":
    print(hello_string)
    rigel = RigelOllama(model_name="llama3.2")
    syslog.info("Started Rigel with model: {}".format(rigel.model))
    messages = [
        ("system", "You are RIGEL, a helpful assistant"),
        ("human", "Say Hello Earth, Let's get the party started!"),
    ]
    syslog.debug(f"Example Inference :{messages}")
    response = rigel.inference(messages=messages)
    syslog.debug(response.content)

    # Online Groq inference
    rigel_groq = RigelGroq(model_name="llama3-70b-8192")
    syslog.info("Started Rigel Groq with model: {}".format(rigel_groq.model))
    messages_groq = [
        ("system", "You are RIGEL, a helpful assistant"),
        ("human", "Say Hello Groq, Let's get the party started!"),
    ]
    syslog.debug(f"Example Inference Groq :{messages_groq}")
    response_groq = rigel_groq.inference(messages=messages_groq)
    syslog.debug(response_groq.content)

    # Example with memory functionality
    syslog.info("Testing memory functionality...")

    # First conversation
    memory_messages_1 = [
        ("human", "My name is John. Remember this!"),
    ]
    syslog.debug(f"Memory Example 1: {memory_messages_1}")
    memory_response_1 = rigel.inference_with_memory(messages=memory_messages_1, thread_id="randomNumberGoesHere")
    syslog.debug(f"Response 1: {memory_response_1.content}")

    # Second conversation - should remember the name
    memory_messages_2 = [
        ("human", "What's my name?"),
    ]
    syslog.debug(f"Memory Example 2: {memory_messages_2}")
    memory_response_2 = rigel.inference_with_memory(messages=memory_messages_2, thread_id="randomNumberGoesHere")
    syslog.debug(f"Response 2: {memory_response_2.content}")

    # Show conversation history
    history = rigel.get_conversation_history(thread_id="randomNumberGoesHere")
    syslog.debug(f"Conversation history: {len(history)} messages")

    # Clear memory example
    rigel.clear_memory(thread_id="randomNumberGoesHere")
    syslog.info("Memory functionality test completed")
    
    # OS Tools examples
    if OS_TOOLS_AVAILABLE:
        syslog.info("Testing OS Tools functionality...")
        
        # Execute a simple command
        cmd_result = rigel.execute_command("ls -la")
        syslog.debug(f"Command execution result: {cmd_result['success']}")
        syslog.debug(f"Command output: {cmd_result.get('stdout', '')[:100]}...")
        
        # Create and execute a temporary Python program
        python_code = """
import os
import platform
import sys

print("Hello from a temporary Python program!")
print(f"Python version: {platform.python_version()}")
print(f"Arguments: {sys.argv[1:]}")
print(f"Current directory: {os.getcwd()}")
"""
        
        program_result = rigel.create_and_execute_program(
            content=python_code,
            args=["arg1", "arg2"],
            cleanup=True
        )
        
        syslog.debug(f"Program execution result: {program_result['success']}")
        syslog.debug(f"Program output: {program_result.get('stdout', '')}")
        
        # Get detailed system information
        sys_info = rigel.get_detailed_system_info()
        syslog.debug(f"System info example: Python version: {sys_info.get('info', {}).get('python', {}).get('version', 'unknown')}")
        
        syslog.info("OS Tools functionality test completed")
        
    else:
        syslog.warning("OS Tools not available for testing")
