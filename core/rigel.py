from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from logger import SysLog
import os
import getpass
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
syslog = SysLog(name="RigelEngine", level="DEBUG", log_file="rigel.log")
hello_string = "Zerone Laboratories Systems - RIGEL Engine v4.0[Alpha]\n"

class Rigel: # RIGEL Super Class. Use this to create derived classes for Thinking, MCP, Vision, etc.
    def __init__(self, model_name: str = "llama3.2", chatmode: str = "ollama"):
        self.model = model_name
        self.chatmode = chatmode
        self.llm = None
        self.messages = None
        self.chain = None

    def inference(self, messages: list, model: str = None):
        self.messages = messages
        """
        Input should be in following format:
        [
            (
                "system",
                "You are a helpful assistant that translates {input_language} to {output_language}.",
            ),
            (   "human", "{input}"
            ),
        ]
        """

        self.prompt = ChatPromptTemplate.from_messages(self.messages)
        self.chain = self.prompt | self.llm
        response = self.chain.invoke({})
        return AIMessage(content=response.content)
    

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