from graphiti_core.embedder.openai import DEFAULT_EMBEDDING_MODEL  # type: ignore

from graph_service.config import Settings
from graph_service.zep_graphiti import build_model_clients


def test_build_model_clients_applies_explicit_overrides():
    settings = Settings(
        openai_api_key='gateway-key',
        openai_base_url='https://ai-gateway.vercel.sh/v1',
        model_name='openai/gpt-4.1-mini',
        small_model_name='openai/gpt-4.1-nano',
        embedding_model_name='openai/text-embedding-3-small',
        neo4j_uri='bolt://localhost:7687',
        neo4j_user='neo4j',
        neo4j_password='password',
    )

    llm_client, embedder, cross_encoder = build_model_clients(settings)

    assert llm_client.config.api_key == 'gateway-key'
    assert llm_client.config.base_url == 'https://ai-gateway.vercel.sh/v1'
    assert llm_client.model == 'openai/gpt-4.1-mini'
    assert llm_client.small_model == 'openai/gpt-4.1-nano'

    assert embedder.config.api_key == 'gateway-key'
    assert embedder.config.base_url == 'https://ai-gateway.vercel.sh/v1'
    assert embedder.config.embedding_model == 'openai/text-embedding-3-small'

    assert cross_encoder.config.api_key == 'gateway-key'
    assert cross_encoder.config.base_url == 'https://ai-gateway.vercel.sh/v1'
    assert cross_encoder.config.model == 'openai/gpt-4.1-nano'


def test_build_model_clients_preserves_defaults_when_optional_overrides_are_missing():
    settings = Settings(
        openai_api_key='gateway-key',
        neo4j_uri='bolt://localhost:7687',
        neo4j_user='neo4j',
        neo4j_password='password',
    )

    llm_client, embedder, cross_encoder = build_model_clients(settings)

    assert llm_client.config.api_key == 'gateway-key'
    assert llm_client.config.base_url is None
    assert llm_client.model is None
    assert llm_client.small_model is None

    assert embedder.config.api_key == 'gateway-key'
    assert embedder.config.base_url is None
    assert embedder.config.embedding_model == DEFAULT_EMBEDDING_MODEL

    assert cross_encoder.config.api_key == 'gateway-key'
    assert cross_encoder.config.base_url is None
    assert cross_encoder.config.model is None
