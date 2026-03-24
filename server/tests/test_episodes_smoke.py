from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from graphiti_core.graphiti import AddEpisodeResults  # type: ignore
from graphiti_core.nodes import EpisodeType  # type: ignore
from graphiti_core.nodes import EpisodicNode  # type: ignore

from graph_service import main as main_module
from graph_service.config import Settings
from graph_service.main import app
from graph_service.zep_graphiti import get_graphiti


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def build_episode(
    *,
    uuid: str,
    name: str,
    group_id: str,
    content: str,
    source: EpisodeType,
    source_description: str,
    valid_at: datetime,
) -> EpisodicNode:
    return EpisodicNode(
        uuid=uuid,
        name=name,
        group_id=group_id,
        source=source,
        source_description=source_description,
        content=content,
        valid_at=valid_at,
        created_at=valid_at,
    )


class FakeGraphiti:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self.episodes_by_uuid: dict[str, EpisodicNode] = {}

    async def add_episode(self, **kwargs: Any) -> AddEpisodeResults:
        self.calls.append(kwargs)
        episode_id = f'episode-{len(self.calls)}'
        episode = build_episode(
            uuid=episode_id,
            name=kwargs['name'],
            group_id=kwargs['group_id'],
            content=kwargs['episode_body'],
            source=kwargs['source'],
            source_description=kwargs['source_description'],
            valid_at=kwargs['reference_time'],
        )
        self.episodes_by_uuid[episode_id] = episode
        return AddEpisodeResults(
            episode=episode,
            episodic_edges=[],
            nodes=[],
            edges=[],
            communities=[],
            community_edges=[],
        )

    async def get_episode(self, uuid: str) -> EpisodicNode:
        return self.episodes_by_uuid[uuid]

    async def get_episodes(self, group_id: str, last_n: int | None = None) -> list[EpisodicNode]:
        episodes = [
            episode for episode in self.episodes_by_uuid.values() if episode.group_id == group_id
        ]
        episodes.sort(key=lambda episode: (episode.valid_at, episode.created_at, episode.uuid), reverse=True)
        if last_n is None:
            return episodes
        return episodes[:last_n]


def test_post_and_get_episodes_contract(monkeypatch):
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

            post_body = response.json()
            assert post_body['episode_id'] == 'episode-1'
            assert post_body['episode']['uuid'] == 'episode-1'
            assert post_body['episode']['group_id'] == 'smoke-group'
            assert post_body['episode']['episode_body'] == '{"kind":"json"}'
            assert post_body['episode']['source'] == 'json'
            assert post_body['episode']['source_description'] == 'smoke-test'
            assert parse_dt(post_body['episode']['reference_time']) == datetime(
                2026, 3, 22, 12, 34, 56, tzinfo=UTC
            )

            second_response = client.post(
                '/episodes',
                json={
                    'group_id': 'smoke-group',
                    'name': 'later-text-episode',
                    'episode_body': 'plain text episode',
                    'source': 'text',
                    'source_description': 'second-write',
                    'reference_time': '2026-03-22T12:35:56Z',
                },
            )
            assert second_response.status_code == 200
            assert second_response.json()['episode_id'] == 'episode-2'

            by_uuid = client.get('/episode/episode-1')
            assert by_uuid.status_code == 200
            assert by_uuid.json()['uuid'] == 'episode-1'
            assert by_uuid.json()['episode_body'] == '{"kind":"json"}'
            assert by_uuid.json()['source'] == 'json'

            by_group = client.get('/episodes/smoke-group')
            assert by_group.status_code == 200
            assert [episode['uuid'] for episode in by_group.json()] == ['episode-2', 'episode-1']
            assert by_group.json()[1]['source'] == 'json'
            assert by_group.json()[1]['episode_body'] == '{"kind":"json"}'

            limited = client.get('/episodes/smoke-group?last_n=1')
            assert limited.status_code == 200
            assert [episode['uuid'] for episode in limited.json()] == ['episode-2']

            openapi = client.get('/openapi.json')
            assert openapi.status_code == 200

            schema = openapi.json()
            assert '/episodes' in schema['paths']
            assert '/episode/{uuid}' in schema['paths']
            assert schema['paths']['/episodes']['post']['summary'] == 'Add a native Graphiti episode'
            assert schema['components']['schemas']['EpisodeType']['enum'] == [
                'message',
                'json',
                'text',
            ]
    finally:
        app.dependency_overrides.clear()
