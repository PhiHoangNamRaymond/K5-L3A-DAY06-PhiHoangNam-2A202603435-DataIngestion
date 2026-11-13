"""Generate multilingual embeddings through the local Ollama API."""

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    def __init__(self, model_name: str = "bge-m3:latest") -> None:
        self.model_name = model_name
        self.dimensions = len(self._embed_batch(["Embedding dimension check"])[0])

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "model": self.model_name,
            "input": texts,
            "truncate": False,
        }
        request = Request(
            "http://127.0.0.1:11434/api/embed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=180) as response:
                vectors = json.load(response)["embeddings"]
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {error.code}: {detail}") from error
        except (URLError, TimeoutError) as error:
            raise RuntimeError(
                f"Cannot reach the Ollama embedding API: {error}"
            ) from error

        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            raise RuntimeError("Ollama returned an unexpected embedding batch")

        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        batch_size = 16

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors.extend(self._embed_batch(batch))

        if any(len(vector) != self.dimensions for vector in vectors):
            raise RuntimeError("Ollama returned an inconsistent embedding dimension")

        return vectors

    def version_info(self) -> dict[str, str]:
        """Record the Ollama server version and the exact model digest."""
        info = {"provider": "Ollama (local)", "model": self.model_name}
        try:
            with urlopen("http://127.0.0.1:11434/api/version", timeout=10) as r:
                info["ollama_version"] = json.load(r)["version"]
            with urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as r:
                for model in json.load(r)["models"]:
                    if model["name"] == self.model_name:
                        info["model_digest"] = model["digest"]
                        info["parameter_size"] = model["details"]["parameter_size"]
                        info["quantization"] = model["details"]["quantization_level"]
        except (URLError, TimeoutError, KeyError) as error:
            info["version_error"] = str(error)
        return info

    def embed_query(self, question: str) -> list[float]:
        return self.embed_documents([question])[0]