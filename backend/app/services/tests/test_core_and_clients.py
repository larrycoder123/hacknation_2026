"""Tests for app.core.llm, app.services.embedding_service, and app.db.client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── app.core.llm ──────────────────────────────────────────────────────


class TestGetLlm:
    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        import app.core.llm as llm_mod
        llm_mod._llm_instance = None
        yield
        llm_mod._llm_instance = None

    @patch("app.core.llm.get_settings")
    @patch("app.core.llm.ChatOpenAI")
    def test_creates_singleton(self, mock_chat, mock_settings):
        import app.core.llm as llm_mod

        mock_settings.return_value = MagicMock(
            openai_model="gpt-4o-mini", openai_api_key="sk-test"
        )
        result = llm_mod.get_llm()
        mock_chat.assert_called_once_with(model="gpt-4o-mini", api_key="sk-test")
        assert result is not None

    @patch("app.core.llm.get_settings")
    @patch("app.core.llm.ChatOpenAI")
    def test_returns_same_instance(self, mock_chat, mock_settings):
        import app.core.llm as llm_mod

        mock_settings.return_value = MagicMock(
            openai_model="gpt-4o-mini", openai_api_key="sk-test"
        )
        first = llm_mod.get_llm()
        second = llm_mod.get_llm()
        assert first is second
        mock_chat.assert_called_once()


class TestGenerateStructuredOutput:
    @patch("app.core.llm.get_llm")
    @pytest.mark.asyncio
    async def test_with_system_prompt(self, mock_get_llm):
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            answer: str

        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke = AsyncMock(
            return_value=TestSchema(answer="42")
        )

        from app.core.llm import generate_structured_output

        result = await generate_structured_output(
            prompt="What is the answer?",
            output_schema=TestSchema,
            system_prompt="You are helpful",
        )
        assert result.answer == "42"
        call_args = mock_structured.ainvoke.call_args[0][0]
        assert call_args[0] == ("system", "You are helpful")

    @patch("app.core.llm.get_settings")
    @patch("app.core.llm.ChatOpenAI")
    @patch("app.core.llm.get_llm")
    @pytest.mark.asyncio
    async def test_with_temperature(self, mock_get_llm, mock_chat_cls, mock_settings):
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            answer: str

        mock_settings.return_value = MagicMock(
            openai_model="gpt-4o-mini", openai_api_key="sk-test"
        )
        # Temperature branch creates a fresh ChatOpenAI, bypassing get_llm
        mock_temp_llm = MagicMock()
        mock_chat_cls.return_value = mock_temp_llm
        mock_structured = MagicMock()
        mock_temp_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke = AsyncMock(
            return_value=TestSchema(answer="warm")
        )

        from app.core.llm import generate_structured_output

        result = await generate_structured_output(
            prompt="question",
            output_schema=TestSchema,
            temperature=0.7,
        )
        assert result.answer == "warm"
        mock_chat_cls.assert_called_once()

    @patch("app.core.llm.get_llm")
    @pytest.mark.asyncio
    async def test_without_system_prompt(self, mock_get_llm):
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            value: int

        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke = AsyncMock(return_value=TestSchema(value=1))

        from app.core.llm import generate_structured_output

        result = await generate_structured_output(
            prompt="count",
            output_schema=TestSchema,
        )
        assert result.value == 1
        call_args = mock_structured.ainvoke.call_args[0][0]
        assert len(call_args) == 1  # Only user message, no system


# ── app.services.embedding_service ─────────────────────────────────────


class TestEmbeddingService:
    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        import app.services.embedding_service as mod
        mod._openai_client = None
        yield
        mod._openai_client = None

    @patch("app.services.embedding_service._get_openai")
    @patch("app.services.embedding_service.get_settings")
    def test_generate_embeddings(self, mock_settings, mock_get_openai):
        mock_settings.return_value = MagicMock(
            embedding_model="text-embedding-3-large",
            embedding_dimension=3072,
        )
        mock_client = MagicMock()
        mock_get_openai.return_value = mock_client

        item0 = MagicMock()
        item0.embedding = [0.1] * 3072
        item1 = MagicMock()
        item1.embedding = [0.2] * 3072
        mock_client.embeddings.create.return_value = MagicMock(data=[item0, item1])

        from app.services.embedding_service import generate_embeddings

        result = generate_embeddings(["text1", "text2"])
        assert len(result) == 2
        assert len(result[0]) == 3072

    @patch("app.services.embedding_service._get_openai")
    @patch("app.services.embedding_service.get_settings")
    def test_generate_embeddings_empty(self, mock_settings, mock_get_openai):
        from app.services.embedding_service import generate_embeddings

        result = generate_embeddings([])
        assert result == []
        mock_get_openai.assert_not_called()

    @patch("app.services.embedding_service._get_openai")
    @patch("app.services.embedding_service.get_settings")
    def test_generate_embedding_single(self, mock_settings, mock_get_openai):
        mock_settings.return_value = MagicMock(
            embedding_model="text-embedding-3-large",
            embedding_dimension=3072,
        )
        mock_client = MagicMock()
        mock_get_openai.return_value = mock_client

        item = MagicMock()
        item.embedding = [0.5] * 3072
        mock_client.embeddings.create.return_value = MagicMock(data=[item])

        from app.services.embedding_service import generate_embedding

        result = generate_embedding("hello")
        assert len(result) == 3072

    @patch("app.services.embedding_service.get_settings")
    @patch("app.services.embedding_service.OpenAI")
    def test_get_openai_creates_client(self, mock_openai_cls, mock_settings):
        import app.services.embedding_service as mod

        mock_settings.return_value = MagicMock(openai_api_key="sk-test")
        client = mod._get_openai()
        mock_openai_cls.assert_called_once_with(api_key="sk-test")
        assert client is not None


# ── app.db.client ──────────────────────────────────────────────────────


class TestDbClient:
    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        import app.db.client as db_mod
        db_mod._supabase_instance = None
        yield
        db_mod._supabase_instance = None

    @patch("app.db.client.create_client")
    @patch("app.db.client.get_settings")
    def test_creates_client(self, mock_settings, mock_create):
        import app.db.client as db_mod

        mock_settings.return_value = MagicMock(
            supabase_url="https://test.supabase.co",
            supabase_service_role_key="sk-service",
        )
        mock_create.return_value = MagicMock()
        client = db_mod.get_supabase()
        mock_create.assert_called_once_with(
            "https://test.supabase.co", "sk-service"
        )
        assert client is not None

    @patch("app.db.client.create_client")
    @patch("app.db.client.get_settings")
    def test_returns_singleton(self, mock_settings, mock_create):
        import app.db.client as db_mod

        mock_settings.return_value = MagicMock(
            supabase_url="https://test.supabase.co",
            supabase_service_role_key="sk-service",
        )
        mock_create.return_value = MagicMock()
        first = db_mod.get_supabase()
        second = db_mod.get_supabase()
        assert first is second
        mock_create.assert_called_once()
