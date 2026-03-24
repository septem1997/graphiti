from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from graph_service import main as main_module
from graph_service.config import Settings
from graph_service.dto import FactResult
from graph_service.dto.episodes import EpisodeResponse
from graph_service.main import app
from graph_service.routers import ingest as ingest_module
from graph_service.zep_graphiti import get_graphiti


class FakeGraphiti:
    def __init__(self):
        self.search_calls: list[dict[str, Any]] = []
        self.edge_fact_calls: list[dict[str, Any]] = []

    async def search_facts(self, **kwargs: Any) -> list[FactResult]:
        self.search_calls.append(kwargs)
        return [
            FactResult(
                uuid='edge-1',
                name='lives_in',
                fact='Alice lives in Shanghai',
                group_id='memory-group',
                source_node_uuid='entity-alice',
                target_node_uuid='entity-shanghai',
                valid_at=datetime(2026, 3, 24, 8, 0, 0, tzinfo=UTC),
                invalid_at=None,
                created_at=datetime(2026, 3, 24, 8, 0, 0, tzinfo=UTC),
                expired_at=None,
                score=0.98,
                episode_uuids=['episode-1'],
                episodes=[
                    EpisodeResponse(
                        uuid='episode-1',
                        name='memory_fact_v1',
                        group_id='memory-group',
                        episode_body='{"factType":"profile","dedupeKey":"alice:city","value":"Shanghai"}',
                        source='json',
                        source_description='memory-fact',
                        reference_time=datetime(2026, 3, 24, 8, 0, 0, tzinfo=UTC),
                    )
                ],
            )
        ]

    async def get_entity_edge(self, uuid: str) -> dict[str, str]:
        return {'uuid': uuid}

    async def get_fact_result(self, edge: dict[str, str], **kwargs: Any) -> FactResult:
        self.edge_fact_calls.append({'edge': edge, **kwargs})
        return FactResult(
            uuid=edge['uuid'],
            name='lives_in',
            fact='Alice lives in Shanghai',
            group_id='memory-group',
            source_node_uuid='entity-alice',
            target_node_uuid='entity-shanghai',
            valid_at=datetime(2026, 3, 24, 8, 0, 0, tzinfo=UTC),
            invalid_at=None,
            created_at=datetime(2026, 3, 24, 8, 0, 0, tzinfo=UTC),
            expired_at=None,
            score=None,
            episode_uuids=['episode-1'],
            episodes=[
                EpisodeResponse(
                    uuid='episode-1',
                    name='memory_fact_v1',
                    group_id='memory-group',
                    episode_body='{"factType":"profile","dedupeKey":"alice:city","value":"Shanghai"}',
                    source='json',
                    source_description='memory-fact',
                    reference_time=datetime(2026, 3, 24, 8, 0, 0, tzinfo=UTC),
                )
            ],
        )


def test_search_rich_contract(monkeypatch):
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
    monkeypatch.setattr(ingest_module, 'async_worker', ingest_module.AsyncWorker())
    app.dependency_overrides[get_graphiti] = fake_get_graphiti

    try:
        with TestClient(app) as client:
            search_response = client.post(
                '/search',
                json={
                    'group_ids': ['memory-group'],
                    'query': 'Where does Alice live?',
                    'max_facts': 5,
                    'only_active': True,
                    'include_linked_episodes': True,
                    'max_linked_episodes_per_fact': 2,
                },
            )
            assert search_response.status_code == 200

            search_call = fake_graphiti.search_calls[0]
            assert search_call['group_ids'] == ['memory-group']
            assert search_call['query'] == 'Where does Alice live?'
            assert search_call['max_facts'] == 5
            assert search_call['only_active'] is True
            assert search_call['include_linked_episodes'] is True
            assert search_call['max_linked_episodes_per_fact'] == 2

            fact = search_response.json()['facts'][0]
            assert fact['score'] == 0.98
            assert fact['group_id'] == 'memory-group'
            assert fact['source_node_uuid'] == 'entity-alice'
            assert fact['target_node_uuid'] == 'entity-shanghai'
            assert fact['episode_uuids'] == ['episode-1']
            assert fact['episodes'][0]['episode_body'] == (
                '{"factType":"profile","dedupeKey":"alice:city","value":"Shanghai"}'
            )

            get_memory_response = client.post(
                '/get-memory',
                json={
                    'group_id': 'memory-group',
                    'max_facts': 3,
                    'center_node_uuid': None,
                    'messages': [
                        {
                            'content': 'Where does Alice live?',
                            'role': 'user',
                            'role_type': 'user',
                            'timestamp': '2026-03-24T08:00:00Z',
                        }
                    ],
                },
            )
            assert get_memory_response.status_code == 200
            assert get_memory_response.json()['facts'][0]['episodes'][0]['uuid'] == 'episode-1'

            entity_edge_response = client.get('/entity-edge/edge-1')
            assert entity_edge_response.status_code == 200
            assert entity_edge_response.json()['episode_uuids'] == ['episode-1']

            openapi = client.get('/openapi.json')
            assert openapi.status_code == 200

            schema = openapi.json()
            search_query_schema = schema['components']['schemas']['SearchQuery']
            fact_result_schema = schema['components']['schemas']['FactResult']

            assert 'only_active' in search_query_schema['properties']
            assert 'include_linked_episodes' in search_query_schema['properties']
            assert 'max_linked_episodes_per_fact' in search_query_schema['properties']
            assert 'group_id' in fact_result_schema['properties']
            assert 'source_node_uuid' in fact_result_schema['properties']
            assert 'target_node_uuid' in fact_result_schema['properties']
            assert 'score' in fact_result_schema['properties']
            assert 'episode_uuids' in fact_result_schema['properties']
            assert 'episodes' in fact_result_schema['properties']
    finally:
        app.dependency_overrides.clear()
