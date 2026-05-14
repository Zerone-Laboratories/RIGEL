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

from version import VERSION

__RIGEL = f"""
RIGEL V{VERSION} - Main Source
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
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from core.logger import SysLog
import os
import glob
import getpass
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
from core.rdb import DBConn
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from pathlib import Path

# Import OSTools if available
try:
    from core.os_tools import OSTools
    OS_TOOLS_AVAILABLE = True
except ImportError:
    OS_TOOLS_AVAILABLE = False


syslog = SysLog(name="RigelEngine", level="DEBUG", log_file="rigel.log")
hello_string = f"Zerone Laboratories Systems - RIGEL Engine v{VERSION}[Alpha]\n"
RIGEL_STREAM_DIR = Path(os.getenv("RIGEL_STREAM_DIR", "/home/zerone/.rigel"))
default_mcp = MultiServerMCPClient(
            {
                "rigel tools": {
                    "url": "http://rigel-tools-server:8001/sse",
                    "transport": "sse",
                }
            },
        )

class Rigel: # RIGEL Super Class. Use this to create derived classes
    def __init__(self, model_name: str = "llama3.2", chatmode: str = "ollama", mcp_endpoint = default_mcp):
        self.model = model_name
        self.chatmode = chatmode
        self.llm = None
        self.messages = None
        self.chain = None
        self.thought_prompt = None
        self.workflow = StateGraph(state_schema=MessagesState)
        self.memory = None
        self.app = None
        self.agent = None
        self.client = None
        self.ragdb = None
        self._initialized = False
        self.tools_memory_store: Dict[str, List[Dict[str, str]]] = {}
        self.vectorstore = DBConn()
        print("VectorStore Preflight")
        self.vectorstore.search_session_context(session_id='1234', query="preflight", n_results=10)
        self.server_params = StdioServerParameters(
            command="python",
            args=["/home/zerone/Projects/RIGEL_SERVICE/core/mcp/rigel_tools_server.py"],
        )
        self.continuity_breakers = [
            r"The task is done\.",
            r"Please provide more information\.",
            r"The task is impossible\.",
            r"Let me know what you'd like to do next\.",
            r"Let me know\.",
            r"I'm unable to continue",
            r"I can't proceed",
            r"I cannot proceed",
            r"Unable to continue",
            r"No specific action to perform",
            r"Could you specify what action you'd like me to take next\?",
            r"Could you please provide more information on what exactly you want to do\?",
            r"Would you like me to help you with anything else\?",
            r"It seems we're stuck",
            r"Let me know how you'd like to proceed!"
        ]
        self.continuity = f"""
                        Proceed. You CAN run code on my machine.
                        ALWAYS run  the command in the 'Working Directory' and remember the working directory
                        When providing tool outputs (like file listings, command results, etc.), always include the actual output in your response.
                        If the entire task I asked for is done, say exactly 'The task is done.' after providing all relevant outputs and results.
                        If you need some specific information (like username or password) say EXACTLY 'Please provide more information.'
                        If it's impossible, say 'The task is impossible.'
                        (If I haven't provided a task, say exactly 'Let me know what you'd like to do next.') Otherwise keep going.
                        Strictly use following continuity breakers
                        {', '.join(self.continuity_breakers)}
        """

        self.think_n_plan = """
        Analyse and try to find the best and optimum way to do a specific problem that the user requested. If the thinking process is done,
        Say exactly 'Task is done'. If its impossible exactly say 'Task is impossible'.
        """

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




    def _escape_template_braces(self, messages: list) -> list:
        """Escape curly braces in message content to prevent LangChain from interpreting them as template variables."""
        escaped = []
        for msg in messages:
            if isinstance(msg, (tuple, list)) and len(msg) == 2:
                role, content = msg
                if isinstance(content, str):
                    content = content.replace('{', '{{').replace('}', '}}')
                escaped.append((role, content))
            elif isinstance(msg, dict) and 'content' in msg:
                content = msg['content']
                if isinstance(content, str):
                    content = content.replace('{', '{{').replace('}', '}}')
                escaped.append({**msg, 'content': content})
            elif hasattr(msg, 'content') and isinstance(msg.content, str):
                escaped.append(msg)
            else:
                escaped.append(msg)
        return escaped

    def inference(self, messages: list, model: str = None, RAG: bool = False):
        self.messages = self._escape_template_braces(messages)
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
        response_text = response.content if hasattr(response, "content") else str(response)
        self._write_method_stream_file("inference", response_text)
        return AIMessage(content=response_text)

    def _prepare_method_stream_file(self, method_name: str) -> str:
        stream_dir = RIGEL_STREAM_DIR
        stream_dir.mkdir(parents=True, exist_ok=True)
        for existing in stream_dir.glob(f"inference-{method_name}-*.stream"):
            try:
                existing.unlink()
            except Exception as e:
                syslog.warning(f"Failed to remove old stream file {existing}: {e}")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return str(stream_dir / f"inference-{method_name}-{timestamp}.stream")

    def _write_method_stream_file(self, method_name: str, content: str) -> str:
        stream_path = self._prepare_method_stream_file(method_name)
        with open(stream_path, "w", encoding="utf-8") as stream_file:
            stream_file.write(content or "")
            stream_file.flush()
        syslog.info(f"{method_name} output written to: {stream_path}")
        return stream_path

    def _chunk_to_text(self, chunk: Any) -> str:
        if chunk is None:
            return ""
        if isinstance(chunk, str):
            return chunk

        content = getattr(chunk, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    value = item.get("text") or item.get("content")
                    if isinstance(value, str):
                        parts.append(value)
            return "".join(parts)
        return str(content) if content else ""

    def inference_stream(self, messages: list, model: str = None, method_name: str = "inference", stream_path: str = None) -> AIMessage:
        self.messages = self._escape_template_braces(messages)
        if model and hasattr(self.llm, "model"):
            self.llm.model = model

        self.prompt = ChatPromptTemplate.from_messages(self.messages)
        self.chain = self.prompt | self.llm
        target_stream_path = stream_path or self._prepare_method_stream_file(method_name)

        collected_tokens: List[str] = []
        with open(target_stream_path, "w", encoding="utf-8") as stream_file:
            for chunk in self.chain.stream({}):
                token = self._chunk_to_text(chunk)
                if not token:
                    continue
                collected_tokens.append(token)
                stream_file.write(token)
                stream_file.flush()

        response_text = "".join(collected_tokens)
        syslog.info(f"Streaming {method_name} complete. Stream written to: {target_stream_path}")
        return AIMessage(content=response_text)

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
            await self.__init_mcp()

        messages = [
            SystemMessage(content=self.continuity),
            {"role": "user", "content": prompt}
        ]

        max_iterations = 10
        iteration_count = 0
        complete_output = []
        previous_response_content = None
        stream_path = self._prepare_method_stream_file("inference_with_tools")

        def _finalize_tools_response(text: str) -> AIMessage:
            with open(stream_path, "w", encoding="utf-8") as stream_file:
                stream_file.write(text or "")
                stream_file.flush()
            syslog.info(f"inference_with_tools output written to: {stream_path}")
            return AIMessage(content=text)

        try:
            while iteration_count < max_iterations:
                iteration_count += 1
                syslog.info(f"Inference iteration {iteration_count}")
                for i in range(0,2):
                    try:
                        result = await self.agent.ainvoke({"messages": messages})
                        break
                    except Exception as e:
                        syslog.error(f"Inference Failed !, Retrying... Error: {str(e)}")
                        result = f"Error occured with inference !"
                        pass
                new_messages = result["messages"][len(messages):]

                iteration_output = []
                for msg in new_messages:
                    if hasattr(msg, 'content') and msg.content:
                        iteration_output.append(str(msg.content))
                    elif hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            if isinstance(tool_call, dict):
                                tool_name = tool_call.get('name', 'unknown')
                                iteration_output.append(f"Tool: {tool_name}")
                    elif hasattr(msg, 'name') and hasattr(msg, 'content'):
                        iteration_output.append(f"Tool Result ({msg.name}): {msg.content}")
                    else:
                        # Safe conversion to string regardless of the object type
                        iteration_output.append(str(msg))

                final_message = result["messages"][-1]
                syslog.info(f"Currently Processing: {final_message}")

                if iteration_output:
                    complete_output.extend(iteration_output)
                if hasattr(final_message, 'content') and final_message.content:
                    response_content = final_message.content.strip()

                    continuity_breaker_found = False
                    for pattern in self.continuity_patterns:
                        if pattern.search(response_content):
                            syslog.info(f"Continuity breaker detected: {response_content}")
                            continuity_breaker_found = True
                            break

                    if not continuity_breaker_found and previous_response_content and response_content == previous_response_content:
                        syslog.info("Repeated response detected; terminating tool loop early.")
                        full_response = "\n\n".join(complete_output)
                        return _finalize_tools_response(f"{full_response}\n\nTask execution terminated due to repeated output.")

                    previous_response_content = response_content

                    if continuity_breaker_found:
                        full_response = "\n\n".join(complete_output)
                        return _finalize_tools_response(full_response)

                    syslog.info(f"No continuity breaker detected. Current output: {response_content}")
                    syslog.info(f"Continuing with task execution (iteration {iteration_count})")
                    messages = result["messages"]
                    messages.append({"role": "user", "content": "Continue with the task."})

                else:
                    return _finalize_tools_response("\n\n".join(complete_output))

            syslog.warning(f"Reached maximum iterations ({max_iterations}) without continuity breaker")
            if complete_output:
                full_response = "\n\n".join(complete_output)
                return _finalize_tools_response(f"{full_response}\n\nTask execution reached maximum iterations ({max_iterations}) without completion.")
            else:
                return _finalize_tools_response(f"Task execution reached maximum iterations ({max_iterations}) without completion.")

        except Exception as e:
            syslog.error(f"Error in inference_with_tools: {e}")
            if complete_output:
                full_response = "\n\n".join(complete_output)
                return _finalize_tools_response(f"{full_response}\n\nError occurred during tool-based inference: {str(e)}")
            else:
                return _finalize_tools_response(f"Error occurred during tool-based inference: {str(e)}")
        finally:
            syslog.info("Cleaning Up MCP")
            await self.cleanup_mcp()

    def _build_tools_memory_context(self, thread_id: str, max_turns: int = 8) -> str:
        turns = self.tools_memory_store.get(thread_id, [])
        if not turns:
            return ""

        context_lines = []
        for turn in turns[-max_turns:]:
            context_lines.append(f"User: {turn.get('user', '')}")
            context_lines.append(f"Assistant: {turn.get('assistant', '')}")
        return "\n".join(context_lines)

    async def inference_with_tools_and_memory(self, prompt: str, thread_id: str = "default"):
        history_context = self._build_tools_memory_context(thread_id)
        if history_context:
            full_prompt = (
                "Conversation history:\n"
                f"{history_context}\n\n"
                "Current user request:\n"
                f"{prompt}"
            )
        else:
            full_prompt = prompt

        response = await self.inference_with_tools(full_prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        thread_history = self.tools_memory_store.setdefault(thread_id, [])
        thread_history.append({"user": prompt, "assistant": response_text})
        if len(thread_history) > 20:
            del thread_history[:-20]

        return response

    def clear_tools_memory(self, thread_id: str = "default"):
        if thread_id in self.tools_memory_store:
            del self.tools_memory_store[thread_id]
            syslog.info(f"Cleared tools memory for thread: {thread_id}")

    def inference_with_memory(self, messages: list, model: str = None, thread_id: str = "default", RAG: bool = True):
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
        summerization_agent_message = """
        - Disable Reasoning: True
        - Disable think loop: True 
        You are a summerization agent. you will receive data from a vectordb,
        you have to provide a summary of those previous interactions.
        """

        if os.getenv("SUMMARIZE_CONVERSATIONS", "false").lower() == "true":
            history = self.get_conversation_history(thread_id)
            if len(history) >= 10:
                syslog.info(f"Summarizing conversation history for thread {thread_id} and clearing memory.")
                history_text = "\n".join([f"{getattr(msg, 'type', 'unknown')}: {getattr(msg, 'content', '')}" for msg in history])
                
                summarization_prompt = [
                    ("system", summerization_agent_message),
                    ("human", f"Here is the conversation history:\n\n{history_text}\n\nPlease provide a concise summary of this conversation to act as permenant memory context.")
                ]
                summary_response = self.inference(summarization_prompt)
                
                self.vectorstore.save_session_turn(
                    session_id=thread_id,
                    user_text="Conversation Summary",
                    assistant_text=summary_response.content if hasattr(summary_response, "content") else str(summary_response),
                    source="conversation-summary"
                )
                self.clear_memory(thread_id)

        # if RAG:
        #     data = self.ragdb.run_similar_search(next((msg for role, msg in messages if role == "human"), ""))
        #     syslog.info(f"RAG Data Retrieved: {data}")
        #     messages.append(("RAG",f"{data}"))

        if RAG:
            syslog.info(f"RIGEL has previous session contexts")
            last_message = messages[-1][1]
            data = self.vectorstore.search_session_context(session_id=thread_id, query=last_message, n_results=10)
            # Escape literal curly braces to prevent Langchain prompt formatting errors
            data = data.replace('{', '{{').replace('}', '}}')

            summarization_prompt = [
                ("system", summerization_agent_message),
                ("human", f"Here is some retrieved context from the database:\n\n{data}\n\nPlease provide a concise summary of this information that might be relevant to the user's query.")
            ]

        
            summerization_agent_call = self.inference(
                summarization_prompt
            )
            # Create session if not exist
            # if not thread_id in self.vector_store_sessions:
            #     self.vector_store_sessions[thread_id] = ClientSession(self.server_params)
            #     syslog.info(f"Created new MCP session for thread_id: {thread_id}")

        formatted_messages = []
        for role, content in messages:
            if role == "system":
                syslog.info(f"Adding system message: {content}")
                current_time = datetime.now().isoformat()
                time_context = f"\n\n<CurrentTime>\nThe current system time is: {current_time}\n</CurrentTime>"
                rag_summary = ("\n\n<PermenantMemoryRecall>\n" + summerization_agent_call.content + "\n</PermenantMemoryRecall>") if RAG else ""
                system_message = content + time_context + rag_summary
                formatted_messages.append(SystemMessage(content=system_message))
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
        # Add content to vectordb
        human = next((msg for role, msg in messages if role == "human"), "")
        assistant = last_message.content if hasattr(last_message, "content") else str(last_message)
        syslog.info(f"[VECTOR-STORE] Adding messagess to vector store. Human: {human}, Assistant: {assistant}")
        self.vectorstore.save_session_turn(
            session_id=thread_id,
            user_text=human,
            assistant_text=assistant,
            source="conversation-history"
        )
        print(f"\n\n\n\n\nSYSTEM_MESSAGE:{system_message}\n\n\n\n\n")
        response_text = last_message.content if hasattr(last_message, "content") else str(last_message)
        self._write_method_stream_file("inference_with_memory", response_text)
        return AIMessage(content=response_text)

    def _setup_workflow(self, system=""):
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
            
    # OS Tools direct integration methods
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

class RigelOllama(Rigel): # RIGEL with ollama backend
    def __init__(self, model_name: str = "llama3.2",  mcp_endpoint = default_mcp):
        super().__init__(model_name=model_name, chatmode="ollama", mcp_endpoint=mcp_endpoint)
        self.ollama_host = os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_URL") or "http://localhost:11434"
        self.llm = self._create_chat_ollama()

    def _create_chat_ollama(self):
        host = self.ollama_host
        model = self.model
        for host_arg in ("base_url", "host", "api_base", "url"):
            try:
                return ChatOllama(model=model, **{host_arg: host}, repeat_penalty=1.3, repeat_last_n=128)
            except TypeError:
                continue
        return ChatOllama(model=model)

    def inference(self, messages: list, model: str = None):
        if model:
            self.llm.model = model
        return super().inference(messages)

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

class RigelTransformers(Rigel): # RIGEL with transformers backend (local inference)
    def __init__(self, model_name: str = "local-transformers-model",  mcp_endpoint = default_mcp):
        super().__init__(model_name=model_name, chatmode="transformers", mcp_endpoint=mcp_endpoint)
        # Initialize your local transformers-based LLM here
        # For example, you could use Hugging Face's transformers library to load a model
        # self.llm = YourLocalTransformersLLM(model_name=self.model)
        syslog.warning("Transformers backend is not implemented yet. This is a placeholder.")

class RigelOllamaStream(RigelOllama): # RIGEL Ollama backend with token streaming to file
    def inference(self, messages: list, model: str = None, stream_path: str = None):
        return self.inference_stream(messages=messages, model=model, method_name="inference", stream_path=stream_path)

class RigelGroqStream(RigelGroq): # RIGEL Groq backend with token streaming to file
    def inference(self, messages: list, model: str = None, stream_path: str = None):
        return self.inference_stream(messages=messages, model=model, method_name="inference", stream_path=stream_path)
  
# class RigelAutoSwap(Rigel):
#     def __init__(self, model_name: str = "llama-swap-model", base_url: str = "http://localhost:12432", temp: float = 0.7):
#         super().__init__(model_name=model_name, chatmode="llama-swap")
#         self.base_url = base_url
#         self.llm = ChatOpenAI(
#             model=self.model,
#             base_url=f"{self.base_url}/v1",
#             api_key="not-needed",
#             temperature=temp,
#         )
#         syslog.info(f"Initialized RIGEL with llama.cpp server at {self.base_url}")


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
