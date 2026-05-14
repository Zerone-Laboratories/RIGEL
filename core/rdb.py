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

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from pypdf import PdfReader
import os
import uuid
from datetime import datetime


class DBConn:
    # Static client to be reused across instances
    _client = None
    
    def __init__(self):
        # Use the static client if it exists, otherwise create it
        if DBConn._client is None:
            DBConn._client = chromadb.PersistentClient(
                path="db/chroma_db",
                settings=chromadb.config.Settings(anonymized_telemetry=False)
            )
        self.chroma_client = DBConn._client
        self.collection = self.chroma_client.get_or_create_collection(name="rag_data")
        self.session_collection = self.chroma_client.get_or_create_collection(name="session_memory")


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

    def run_similar_search(self, query: str):
        results = self.collection.query(query_texts=[query], n_results=3)
        retrieved_text = "\n".join(results["documents"][0]) if results["documents"] else ""
        return retrieved_text

    def save_session_turn(self, session_id: str, user_text: str, assistant_text: str, source: str = "natural-language"):
        if not session_id:
            return

        current_time = datetime.utcnow().isoformat()

        document = (
            f"Time: {current_time}\n"
            f"Session: {session_id}\n"
            f"User: {user_text}\n"
            f"Assistant: {assistant_text}"
        )
        metadata = {
            "session_id": session_id,
            "source": source,
            "timestamp": current_time,
        }

        self.session_collection.add(
            documents=[document],
            ids=[str(uuid.uuid4())],
            metadatas=[metadata],
        )

    def search_session_context(self, session_id: str, query: str, n_results: int = 10) -> str:
        if not session_id:
            return ""

        try:
            results = self.session_collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"session_id": session_id},
            )
        except Exception:
            return ""

        documents = results.get("documents", [])
        if not documents or not documents[0]:
            return ""

        return "\n\n".join(documents[0])
