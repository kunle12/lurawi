"""
This module provides functionality for performing semantic searches using ChromaDB with either
LlamaCpp or OpenAI embedding models. It includes a custom embedding function for LlamaCpp models
and a behavior class for executing semantic search operations.
"""

import os
import numpy as np

from llama_cpp import Llama
from chromadb.config import Settings
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from chromadb import Documents, EmbeddingFunction, Embeddings

from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger, cut_string


class LlamaCppEmbeddingFunction(EmbeddingFunction):
    """A custom embedding function using the LlamaCpp library to generate embeddings for
       text inputs.

    This class wraps the Llama model for embedding generation, enabling integration with ChromaDB.
    """

    def __init__(self, model_path: str):
        """Initialize the embedding function with a specified LlamaCpp model.

        Args:
            model_path (str): The file path to the LlamaCpp model.
        """
        self._client = Llama(
            model_path, embedding=True, n_ctx=4096, n_gpu_layers=256, verbose=False
        )

    def __call__(self, text_inputs: Documents) -> Embeddings:
        """Generate embeddings for a list of text inputs.

        Args:
            text_inputs (Documents): A list of text strings to be embedded.

        Returns:
            Embeddings: A list of NumPy arrays representing the embeddings for each input text.
        """
        embeddings = []
        for text in text_inputs:
            embeddings.append(self._client.embed(text))
        return [np.array(embedding, dtype=np.float32) for embedding in embeddings]


class chromadb_search(CustomBehaviour):
    """!@brief Executes semantic search operations via ChromaDB with robust error handling,
    manages knowledge base (KB) storage for search results, and enforces token
    limits on output documents.
    Example:
    ["custom", { "name": "chromadb_search",
                 "args": {
                            "base_url": "https://api.openai.com/v1",
                            "api_key": "OPENAI_API_KEY",
                            "collection": "db collection name",
                            "directory": "optional local db directory",
                            "embedding_model": "embedding model file name",
                            "doc_data": {"chunk_id": "chunked document data"},
                            "max_tokens": 5000,
                            "search_text": "search text",
                            "results": "results from semantic search in chromadb",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    async def run(self):
        base_url = self.parse_simple_input(key="base_url", check_for_type="str")

        api_key = self.parse_simple_input(key="api_key", check_for_type="str")

        collection = self.parse_simple_input(key="collection", check_for_type="str")

        if collection is None:
            logger.error("chromadb_search: missing db collection name")
            await self.failed()
            return

        search_text = self.parse_simple_input(key="search_text", check_for_type="str")

        if search_text is None:
            logger.error("chromadb_search: missing search text")
            await self.failed()
            return

        workspace_dir = self.kb.get("LURAWI_WORKSPACE", ".")

        db_directory = self.parse_simple_input(key="directory", check_for_type="str")

        if db_directory is None:
            logger.error("chromadb_search: missing chromadb directory")
            await self.failed()
            return

        if not os.path.isabs(db_directory):
            db_directory = f"{workspace_dir}/{db_directory}"

        if not os.path.isdir(db_directory):
            logger.error("chromadb_search: missing chromadb directory")
            await self.failed()
            return

        chroma_client = PersistentClient(
            path=db_directory, settings=Settings(anonymized_telemetry=False)
        )
        embedding_model = self.parse_simple_input(
            key="embedding_model", check_for_type="str"
        )

        if embedding_model is None:
            logger.error("chromadb_search: missing embedding model name")
            await self.failed()
            return

        if embedding_model.endswith(".gguf"):  # local llamacpp model file
            model_path = f"{workspace_dir}/{embedding_model}"
            if not os.path.isfile(model_path):
                logger.error("chromadb_search: missing embedding model file")
                await self.failed()
                return
            embedding_function = LlamaCppEmbeddingFunction(model_path=model_path)
        else:
            embedding_function = OpenAIEmbeddingFunction(
                api_base=base_url, api_key=api_key, model_name=embedding_model
            )

        try:
            vector_store = chroma_client.get_collection(
                name=collection, embedding_function=embedding_function
            )
        except ValueError:
            logger.error(
                "chromadb_search: unable to load collection %s from %s",
                collection,
                db_directory,
            )

        doc_data = self.parse_simple_input(key="doc_data", check_for_type="dict")

        max_tokens = self.parse_simple_input(key="max_tokens", check_for_type="int")

        if max_tokens is None:
            max_tokens = -1

        try:
            results = vector_store.query(
                query_texts=[search_text], include=["documents", "metadatas"]
            )

            if doc_data:
                found_doc = "\n".join(
                    [doc_data[result[0].metadata["chunk_id"]] for result in results]
                )
            else:
                found_doc = "\n".join([result[0].page_content for result in results])
        except Exception as err:  # pylint: disable=broad-exception-caught
            logger.error("chromadb_search: semantic search return error: %s", err)
            if "SEMANTICS_SEARCH_RESULTS" in self.kb:
                del self.kb["SEMANTICS_SEARCH_RESULTS"]
            await self.failed()
            return

        if max_tokens > 0:
            found_doc = cut_string(s=found_doc, n_tokens=max_tokens)

        output = self.details.get("output")

        if output and isinstance(output, str):
            self.kb[output] = found_doc
        self.kb["SEMANTICS_SEARCH_RESULTS"] = found_doc
        await self.succeeded()
