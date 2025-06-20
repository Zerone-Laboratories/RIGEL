# This file is part of RIGEL_ENGINE.
#
# RIGEL_ENGINE is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RIGEL_ENGINE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

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