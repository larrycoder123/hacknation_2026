"""Tests for RAG core modules: embedder, llm, reranker, supabase_client."""

from unittest.mock import MagicMock, patch

import pytest

from app.rag.core.llm import LLM, TokenUsage
from app.rag.core.reranker import Reranker, RankedDocument
from app.rag.core.embedder import Embedder


# ── TokenUsage ──────────────────────────────────────────────────────────


class TestTokenUsage:
    def test_defaults(self):
        t = TokenUsage()
        assert t.input == 0
        assert t.output == 0
        assert t.model == ""

    def test_addition(self):
        a = TokenUsage(input=10, output=5, model="a")
        b = TokenUsage(input=20, output=10, model="b")
        c = a + b
        assert c.input == 30
        assert c.output == 15
        assert c.model == "b"

    def test_addition_preserves_model_from_left_when_right_empty(self):
        a = TokenUsage(input=1, output=1, model="left")
        b = TokenUsage(input=2, output=2, model="")
        c = a + b
        assert c.model == "left"


# ── LLM ─────────────────────────────────────────────────────────────────


@patch("app.rag.core.llm.settings")
class TestLLM:
    """All tests share a patched settings module."""

    @pytest.fixture(autouse=True)
    def _setup_settings(self, request):
        """Grab the patched settings from the outermost @patch decorator."""
        # The @patch class decorator injects mock_settings as the last positional arg
        # of each test method. This fixture just sets common defaults.
        pass

    def _configure(self, mock_settings, api_key="sk-test", model="m"):
        mock_settings.openai_api_key = api_key
        mock_settings.openai_chat_model = model

    def test_init_uses_settings(self, mock_settings):
        self._configure(mock_settings, model="gpt-4o-mini")
        llm = LLM()
        assert llm.api_key == "sk-test"
        assert llm.model == "gpt-4o-mini"

    def test_init_custom_params(self, mock_settings):
        self._configure(mock_settings)
        llm = LLM(api_key="sk-custom", model="gpt-4o")
        assert llm.api_key == "sk-custom"
        assert llm.model == "gpt-4o"

    def test_last_usage_initially_none(self, mock_settings):
        self._configure(mock_settings)
        llm = LLM()
        assert llm.last_usage is None
        assert llm.total_usage.input == 0

    def test_reset_usage(self, mock_settings):
        self._configure(mock_settings)
        llm = LLM()
        llm._last_usage = TokenUsage(input=10, output=5)
        llm._total_usage = TokenUsage(input=10, output=5)
        llm.reset_usage()
        assert llm.last_usage is None
        assert llm.total_usage.input == 0

    @patch("app.rag.core.llm.OpenAI")
    def test_client_lazy_loads(self, mock_openai_cls, mock_settings):
        self._configure(mock_settings)
        llm = LLM()
        assert llm._client is None
        _ = llm.client
        mock_openai_cls.assert_called_once_with(api_key="sk-test")

    @patch("app.rag.core.llm.OpenAI")
    def test_chat_plain_text(self, mock_openai_cls, mock_settings):
        self._configure(mock_settings)
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model = "m"
        mock_client.chat.completions.create.return_value = mock_response

        llm = LLM()
        result = llm.chat([{"role": "user", "content": "Hi"}])
        assert result == "Hello"
        assert llm.last_usage.input == 10
        assert llm.last_usage.output == 5

    @patch("app.rag.core.llm.OpenAI")
    def test_chat_structured_output(self, mock_openai_cls, mock_settings):
        self._configure(mock_settings)
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: str

        mock_parsed = TestModel(value="parsed")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(parsed=mock_parsed))]
        mock_response.usage = MagicMock(prompt_tokens=15, completion_tokens=8)
        mock_response.model = "m"
        mock_client.beta.chat.completions.parse.return_value = mock_response

        llm = LLM()
        result = llm.chat(
            [{"role": "user", "content": "parse"}], response_model=TestModel
        )
        assert result.value == "parsed"

    @patch("app.rag.core.llm.OpenAI")
    def test_summarize_calls_chat(self, mock_openai_cls, mock_settings):
        self._configure(mock_settings)
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Summary"))]
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response

        llm = LLM()
        result = llm.summarize("Long text here")
        assert result == "Summary"

    @patch("app.rag.core.llm.OpenAI")
    def test_track_usage_no_usage_attr(self, mock_openai_cls, mock_settings):
        self._configure(mock_settings)
        llm = LLM()
        mock_response = MagicMock(spec=[])  # No 'usage' attribute
        llm._track_usage(mock_response)
        assert llm.last_usage is None


# ── Embedder ─────────────────────────────────────────────────────────────


@patch("app.rag.core.embedder.settings")
class TestEmbedder:
    """All tests share a patched settings module."""

    def _configure(self, mock_settings, dimension=3072):
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_embedding_model = "m"
        mock_settings.embedding_dimension = dimension

    def test_init_defaults(self, mock_settings):
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_embedding_model = "text-embedding-3-large"
        emb = Embedder()
        assert emb.api_key == "sk-test"
        assert emb.model == "text-embedding-3-large"

    @patch("app.rag.core.embedder.OpenAI")
    def test_client_lazy_loads(self, mock_openai_cls, mock_settings):
        self._configure(mock_settings)
        emb = Embedder()
        assert emb._client is None
        _ = emb.client
        mock_openai_cls.assert_called_once_with(api_key="sk-test")

    @patch("app.rag.core.embedder.OpenAI")
    def test_embed_single(self, mock_openai_cls, mock_settings):
        self._configure(mock_settings)
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_item = MagicMock()
        mock_item.embedding = [0.1] * 3072
        mock_response = MagicMock()
        mock_response.data = [mock_item]
        mock_client.embeddings.create.return_value = mock_response

        emb = Embedder()
        result = emb.embed("test text")
        assert len(result) == 3072
        mock_client.embeddings.create.assert_called_once()

    @patch("app.rag.core.embedder.OpenAI")
    def test_embed_batch(self, mock_openai_cls, mock_settings):
        self._configure(mock_settings)
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        item0 = MagicMock()
        item0.index = 0
        item0.embedding = [0.1] * 3072
        item1 = MagicMock()
        item1.index = 1
        item1.embedding = [0.2] * 3072

        mock_response = MagicMock()
        mock_response.data = [item1, item0]  # Out of order
        mock_client.embeddings.create.return_value = mock_response

        emb = Embedder()
        result = emb.embed_batch(["text1", "text2"])
        assert len(result) == 2
        assert result[0][0] == 0.1  # item0 at index 0
        assert result[1][0] == 0.2  # item1 at index 1


# ── Reranker ────────────────────────────────────────────────────────────


@patch("app.rag.core.reranker.settings")
class TestReranker:
    """All tests share a patched settings module."""

    def _configure(self, mock_settings, api_key="co-test"):
        mock_settings.cohere_api_key = api_key
        mock_settings.cohere_rerank_model = "m"

    def test_is_available_true(self, mock_settings):
        self._configure(mock_settings)
        r = Reranker()
        assert r.is_available is True

    def test_is_available_false(self, mock_settings):
        self._configure(mock_settings, api_key="")
        r = Reranker()
        assert r.is_available is False

    def test_rerank_empty_docs(self, mock_settings):
        self._configure(mock_settings)
        r = Reranker()
        result = r.rerank("query", [])
        assert result == []

    def test_rerank_fallback_no_api_key(self, mock_settings):
        self._configure(mock_settings, api_key="")
        r = Reranker()
        result = r.rerank("query", ["doc1", "doc2"], top_k=2)
        assert len(result) == 2
        assert result[0].index == 0
        assert result[0].relevance_score == 1.0
        assert result[1].relevance_score == 0.99

    @patch("app.rag.core.reranker.cohere")
    def test_client_lazy_loads(self, mock_cohere, mock_settings):
        self._configure(mock_settings)
        r = Reranker()
        assert r._client is None
        _ = r.client
        mock_cohere.Client.assert_called_once_with(api_key="co-test")

    @patch("app.rag.core.reranker.cohere")
    def test_rerank_with_api(self, mock_cohere, mock_settings):
        self._configure(mock_settings)
        mock_client = MagicMock()
        mock_cohere.Client.return_value = mock_client

        result0 = MagicMock()
        result0.index = 1
        result0.document.text = "doc2"
        result0.relevance_score = 0.95
        result1 = MagicMock()
        result1.index = 0
        result1.document.text = "doc1"
        result1.relevance_score = 0.80
        mock_client.rerank.return_value = MagicMock(results=[result0, result1])

        r = Reranker()
        ranked = r.rerank("query", ["doc1", "doc2"], top_k=2)
        assert len(ranked) == 2
        assert ranked[0].relevance_score == 0.95
        assert ranked[0].index == 1


# ── Supabase Client ────────────────────────────────────────────────────


class TestSupabaseClient:
    @pytest.fixture(autouse=True)
    def _reset_cache(self):
        from app.rag.core.supabase_client import get_supabase_client
        get_supabase_client.cache_clear()
        yield
        get_supabase_client.cache_clear()

    @patch("app.rag.core.supabase_client.settings")
    def test_raises_without_config(self, mock_settings):
        mock_settings.supabase_url = ""
        mock_settings.supabase_service_role_key = ""
        from app.rag.core.supabase_client import get_supabase_client
        with pytest.raises(ValueError, match="SUPABASE_URL"):
            get_supabase_client()

    @patch("app.rag.core.supabase_client.create_client")
    @patch("app.rag.core.supabase_client.settings")
    def test_creates_client(self, mock_settings, mock_create):
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_service_role_key = "sk-service"
        mock_create.return_value = MagicMock()
        from app.rag.core.supabase_client import get_supabase_client
        client = get_supabase_client()
        mock_create.assert_called_once_with(
            "https://test.supabase.co", "sk-service"
        )
        assert client is not None
