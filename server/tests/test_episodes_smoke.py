from typing import Any

from fastapi.testclient import TestClient
from graphiti_core.graphiti import AddEpisodeResults  # type: ignore
from graphiti_core.nodes import EpisodeType  # type: ignore
from graphiti_core.nodes import EpisodicNode  # type: ignore

from graph_service import main as main_module
from graph_service.config import Settings
from graph_service.main import app
from graph_service.zep_graphiti import get_graphiti


class FakeGraphiti:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def add_episode(self, **kwargs: Any) -> AddEpisodeResults:
        self.calls.append(kwargs)
        return AddEpisodeResults(
            episode=EpisodicNode(
                uuid='episode-1',
                name=kwargs['name'],
                group_id=kwargs['group_id'],
                source=kwargs['source'],
                source_description=kwargs['source_description'],
                content=kwargs['episode_body'],
                valid_at=kwargs['reference_time'],
            ),
            episodic_edges=[],
            nodes=[],
            edges=[],
            communities=[],
            community_edges=[],
        )


def test_post_episodes_smoke(monkeypatch):
    settings = Settings(
        openai_api_key='test-key',
        neo4j_uri='bolt://localhost:7687',
        neo4j_user='neo4j',
        neo4j_password='password',
    )
    fake_graphiti = FakeGraphiti()

    async def fake_initialize_graphiti(_: Settings):
        return None

    async def fake_get_graphiti():
        yield fake_graphiti

    monkeypatch.setattr(main_module, 'initialize_graphiti', fake_initialize_graphiti)
    monkeypatch.setattr(main_module, 'get_settings', lambda: settings)
    app.dependency_overrides[get_graphiti] = fake_get_graphiti

    try:
        with TestClient(app) as client:
            response = client.post(
                '/episodes',
                json={
                    'group_id': 'smoke-group',
                    'name': 'native-json-episode',
                    'episode_body': '{"kind":"json"}',
                    'source': 'json',
                    'source_description': 'smoke-test',
                    'reference_time': '2026-03-22T12:34:56Z',
                    'previous_episode_uuids': ['previous-episode'],
                    'custom_extraction_instructions': 'Prefer exact ids.',
                    'saga': 'daily-sync',
                    'saga_previous_episode_uuid': 'saga-prev',
                },
            )

            assert response.status_code == 200
            assert len(fake_graphiti.calls) == 1

            call = fake_graphiti.calls[0]
            assert call['group_id'] == 'smoke-group'
            assert call['name'] == 'native-json-episode'
            assert call['episode_body'] == '{"kind":"json"}'
            assert call['source'] is EpisodeType.json
            assert call['source_description'] == 'smoke-test'
            assert call['reference_time'].isoformat() == '2026-03-22T12:34:56+00:00'
            assert call['previous_episode_uuids'] == ['previous-episode']
            assert call['custom_extraction_instructions'] == 'Prefer exact ids.'
            assert call['saga'] == 'daily-sync'
            assert call['saga_previous_episode_uuid'] == 'saga-prev'
            assert response.json()['episode']['uuid'] == 'episode-1'
            assert response.json()['episode']['source'] == 'json'

            openapi = client.get('/openapi.json')
            assert openapi.status_code == 200

            schema = openapi.json()
            assert '/episodes' in schema['paths']
            assert schema['paths']['/episodes']['post']['summary'] == 'Add a native Graphiti episode'
            assert schema['components']['schemas']['EpisodeType']['enum'] == [
                'message',
                'json',
                'text',
            ]
    finally:
        app.dependency_overrides.clear()
