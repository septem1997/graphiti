from fastapi import APIRouter, Query, status

from graph_service.dto import (
    EpisodeResponse,
    GetMemoryRequest,
    GetMemoryResponse,
    FactResult,
    Message,
    SearchQuery,
    SearchResults,
)
from graph_service.dto.episodes import episode_response_from_node
from graph_service.zep_graphiti import ZepGraphitiDep

router = APIRouter()


@router.post('/search', status_code=status.HTTP_200_OK)
async def search(query: SearchQuery, graphiti: ZepGraphitiDep):
    facts = await graphiti.search_facts(
        query=query.query,
        group_ids=query.group_ids,
        max_facts=query.max_facts,
        only_active=query.only_active,
        include_linked_episodes=query.include_linked_episodes,
        max_linked_episodes_per_fact=query.max_linked_episodes_per_fact,
    )
    return SearchResults(
        facts=facts,
    )


@router.get('/entity-edge/{uuid}', status_code=status.HTTP_200_OK, response_model=FactResult)
async def get_entity_edge(uuid: str, graphiti: ZepGraphitiDep):
    entity_edge = await graphiti.get_entity_edge(uuid)
    return await graphiti.get_fact_result(entity_edge)


@router.get('/episodes/{group_id}', status_code=status.HTTP_200_OK, response_model=list[EpisodeResponse])
async def get_episodes(
    group_id: str,
    graphiti: ZepGraphitiDep,
    last_n: int | None = Query(default=None, ge=1),
) -> list[EpisodeResponse]:
    episodes = await graphiti.get_episodes(group_id, last_n=last_n)
    return [episode_response_from_node(episode) for episode in episodes]


@router.get('/episode/{uuid}', status_code=status.HTTP_200_OK, response_model=EpisodeResponse)
async def get_episode(uuid: str, graphiti: ZepGraphitiDep):
    episode = await graphiti.get_episode(uuid)
    return episode_response_from_node(episode)


@router.post('/get-memory', status_code=status.HTTP_200_OK)
async def get_memory(
    request: GetMemoryRequest,
    graphiti: ZepGraphitiDep,
):
    combined_query = compose_query_from_messages(request.messages)
    facts = await graphiti.search_facts(
        query=combined_query,
        group_ids=[request.group_id],
        max_facts=request.max_facts,
    )
    return GetMemoryResponse(facts=facts)


def compose_query_from_messages(messages: list[Message]):
    combined_query = ''
    for message in messages:
        combined_query += f'{message.role_type or ""}({message.role or ""}): {message.content}\n'
    return combined_query
