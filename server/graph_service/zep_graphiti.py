import asyncio
import logging
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException
from graphiti_core import Graphiti  # type: ignore
from graphiti_core.edges import EntityEdge  # type: ignore
from graphiti_core.errors import EdgeNotFoundError, GroupsEdgesNotFoundError, NodeNotFoundError
from graphiti_core.llm_client import LLMClient  # type: ignore
from graphiti_core.nodes import EntityNode, EpisodicNode  # type: ignore
from graphiti_core.search.search_config_recipes import EDGE_HYBRID_SEARCH_RRF  # type: ignore

from graph_service.config import ZepEnvDep
from graph_service.dto import FactResult
from graph_service.dto.episodes import EpisodeResponse, episode_response_from_node

logger = logging.getLogger(__name__)


class ZepGraphiti(Graphiti):
    def __init__(self, uri: str, user: str, password: str, llm_client: LLMClient | None = None):
        super().__init__(uri, user, password, llm_client)

    async def save_entity_node(self, name: str, uuid: str, group_id: str, summary: str = ''):
        new_node = EntityNode(
            name=name,
            uuid=uuid,
            group_id=group_id,
            summary=summary,
        )
        await new_node.generate_name_embedding(self.embedder)
        await new_node.save(self.driver)
        return new_node

    async def get_entity_edge(self, uuid: str):
        try:
            edge = await EntityEdge.get_by_uuid(self.driver, uuid)
            return edge
        except EdgeNotFoundError as e:
            raise HTTPException(status_code=404, detail=e.message) from e

    async def delete_group(self, group_id: str):
        try:
            edges = await EntityEdge.get_by_group_ids(self.driver, [group_id])
        except GroupsEdgesNotFoundError:
            logger.warning(f'No edges found for group {group_id}')
            edges = []

        nodes = await EntityNode.get_by_group_ids(self.driver, [group_id])

        episodes = await EpisodicNode.get_by_group_ids(self.driver, [group_id])

        for edge in edges:
            await edge.delete(self.driver)

        for node in nodes:
            await node.delete(self.driver)

        for episode in episodes:
            await episode.delete(self.driver)

    async def delete_entity_edge(self, uuid: str):
        try:
            edge = await EntityEdge.get_by_uuid(self.driver, uuid)
            await edge.delete(self.driver)
        except EdgeNotFoundError as e:
            raise HTTPException(status_code=404, detail=e.message) from e

    async def delete_episodic_node(self, uuid: str):
        try:
            episode = await EpisodicNode.get_by_uuid(self.driver, uuid)
            await episode.delete(self.driver)
        except NodeNotFoundError as e:
            raise HTTPException(status_code=404, detail=e.message) from e

    async def get_episode(self, uuid: str) -> EpisodicNode:
        try:
            return await EpisodicNode.get_by_uuid(self.driver, uuid)
        except NodeNotFoundError as e:
            raise HTTPException(status_code=404, detail=e.message) from e

    async def get_episodes(self, group_id: str, last_n: int | None = None) -> list[EpisodicNode]:
        episodes = await EpisodicNode.get_by_group_ids(self.driver, [group_id])
        episodes.sort(
            key=lambda episode: (
                episode.valid_at,
                episode.created_at if isinstance(episode.created_at, datetime) else episode.valid_at,
                episode.uuid,
            ),
            reverse=True,
        )
        if last_n is None:
            return episodes
        return episodes[:last_n]

    async def get_linked_episode_responses(
        self,
        episode_uuids: list[str],
        max_linked_episodes_per_fact: int,
    ) -> list[EpisodeResponse]:
        if not episode_uuids or max_linked_episodes_per_fact <= 0:
            return []

        selected_episode_uuids = episode_uuids[:max_linked_episodes_per_fact]
        linked_episodes = await EpisodicNode.get_by_uuids(self.driver, selected_episode_uuids)
        episodes_by_uuid = {episode.uuid: episode for episode in linked_episodes}
        return [
            episode_response_from_node(episodes_by_uuid[episode_uuid])
            for episode_uuid in selected_episode_uuids
            if episode_uuid in episodes_by_uuid
        ]

    async def get_fact_result(
        self,
        edge: EntityEdge,
        score: float | None = None,
        include_linked_episodes: bool = True,
        max_linked_episodes_per_fact: int = 3,
    ) -> FactResult:
        linked_episodes = []
        if include_linked_episodes:
            linked_episodes = await self.get_linked_episode_responses(
                edge.episodes,
                max_linked_episodes_per_fact=max_linked_episodes_per_fact,
            )

        return FactResult(
            uuid=edge.uuid,
            name=edge.name,
            fact=edge.fact,
            group_id=edge.group_id,
            source_node_uuid=edge.source_node_uuid,
            target_node_uuid=edge.target_node_uuid,
            valid_at=edge.valid_at,
            invalid_at=edge.invalid_at,
            created_at=edge.created_at,
            expired_at=edge.expired_at,
            score=float(score) if score is not None else None,
            episode_uuids=edge.episodes,
            episodes=linked_episodes,
        )

    async def search_facts(
        self,
        query: str,
        group_ids: list[str] | None,
        max_facts: int = 10,
        only_active: bool = False,
        include_linked_episodes: bool = True,
        max_linked_episodes_per_fact: int = 3,
    ) -> list[FactResult]:
        search_config = EDGE_HYBRID_SEARCH_RRF.model_copy(deep=True)
        search_config.limit = max_facts

        search_results = await self.search_(
            query=query,
            config=search_config,
            group_ids=group_ids,
        )

        filtered_edges_with_scores = []
        for index, edge in enumerate(search_results.edges):
            if only_active and (edge.invalid_at is not None or edge.expired_at is not None):
                continue
            score = (
                search_results.edge_reranker_scores[index]
                if index < len(search_results.edge_reranker_scores)
                else None
            )
            filtered_edges_with_scores.append((edge, score))

        return await asyncio.gather(
            *[
                self.get_fact_result(
                    edge,
                    score=score,
                    include_linked_episodes=include_linked_episodes,
                    max_linked_episodes_per_fact=max_linked_episodes_per_fact,
                )
                for edge, score in filtered_edges_with_scores
            ]
        )


async def get_graphiti(settings: ZepEnvDep):
    client = ZepGraphiti(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    if settings.openai_base_url is not None:
        client.llm_client.config.base_url = settings.openai_base_url
    if settings.openai_api_key is not None:
        client.llm_client.config.api_key = settings.openai_api_key
    if settings.model_name is not None:
        client.llm_client.model = settings.model_name
    try:
        yield client
    finally:
        await client.close()


async def initialize_graphiti(settings: ZepEnvDep):
    client = ZepGraphiti(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    await client.build_indices_and_constraints()


ZepGraphitiDep = Annotated[ZepGraphiti, Depends(get_graphiti)]
