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
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from logger import SysLog
import os
import getpass
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
syslog = SysLog(name="RigelEngine", level="DEBUG", log_file="rigel.log")
hello_string = "Zerone Laboratories Systems - RIGEL Engine v4.0[Alpha]\n"

class Rigel: # RIGEL Super Class. Use this to create derived classes
    def __init__(self, model_name: str = "llama3.2", chatmode: str = "ollama"):
        self.model = model_name
        self.chatmode = chatmode
        self.llm = None
        self.messages = None
        self.chain = None
        self.thought_prompt = None
        self.workflow = StateGraph(state_schema=MessagesState)
        self.memory = None
        self.app = None


    def inference(self, messages: list, model: str = None):
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
        response = self.chain.invoke({})
        return AIMessage(content=response.content)
    
    def inference_with_tools(self, messages: list, tools: list, model: str = None):
        "[TODO]"
        return 0
    
    def inference_with_memory(self, messages: list, model: str = None, thread_id: str = "default"):
        """
        use this function as follows
        
        Args:
            messages: List of messages in format [("role", "content"), ...]
            model: Optional model name override
            thread_id: Thread ID for conversation memory
        
        Returns:
            AIMessage with response content
        """
        if not self.app:
            self._setup_workflow()
        
        formatted_messages = []
        for role, content in messages:
            if role == "system":
                formatted_messages.append(SystemMessage(content=content))
            elif role == "human":
                formatted_messages.append({"role": "user", "content": content})
            elif role == "ai":
                formatted_messages.append({"role": "assistant", "content": content})
        
        config = {"configurable": {"thread_id": thread_id}}
        response = self.app.invoke(
            {"messages": formatted_messages},
            config=config
        )
        last_message = response["messages"][-1]
        return AIMessage(content=last_message.content)
    
    def _setup_workflow(self):
        def call_model(state: MessagesState):
            system_prompt = (
                "You are RIGEL, a helpful assistant. "
                "Answer all questions to the best of your ability."
            )
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
        output = self.inference(self.prompt)
        return output
    
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

class RigelOllama(Rigel): # RIGEL with ollama backend
    def __init__(self, model_name: str = "llama3.2"):
        super().__init__(model_name=model_name, chatmode="ollama")
        self.llm = ChatOllama(model=self.model)
    
    def inference(self, messages: list, model: str = None):
        if model:
            self.llm.model = model
        return super().inference(messages)

class RigelGroq(Rigel): # RIGEL with groq backend
    def __init__(self, model_name: str = "llama3-70b-8192", temp: float = 0.7):
        super().__init__(model_name=model_name, chatmode="groq")
        if "GROQ_API_KEY" not in os.environ:
            os.environ["GROQ_API_KEY"] = getpass.getpass("Enter your Groq API key: ")
        self.llm = ChatGroq(model=self.model,
                            temperature=temp,
                            )

    def inference(self, messages: list, model: str = None):
        if model:
            self.llm.model = model
        return super().inference(messages)
    


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