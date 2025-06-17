import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from pypdf import PdfReader
import os


class DBConn:
    def __init__(self):
        self.chroma_client = chromadb.PersistentClient(path="db/chroma_db")
        self.collection = self.chroma_client.get_or_create_collection(name="rag_data")
        

    def load_data_from_pdf_path(self, path: str):
        reader = PdfReader(path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                self.collection.add(documents=[text], ids=[str(i)])

    def load_data_from_txt_path(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
                if content.strip():
                    filename = os.path.basename(path)
                    self.collection.add(documents=[content], ids=[filename])
        except FileNotFoundError:
            print(f"Error: File not found at path: {path}")
        except Exception as e:
            print(f"Error reading file {path}: {str(e)}")

    def run_similar_serch(self, query: str):
        results = self.collection.query(query_texts=[query], n_results=3)
        retrieved_text = "\n".join(results["documents"][0]) if results["documents"] else ""
        return retrieved_text