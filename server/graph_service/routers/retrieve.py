from fastapi import APIRouter, Query, status

from graph_service.dto import (
    EpisodeResponse,
    GetMemoryRequest,
    GetMemoryResponse,
    Message,
    SearchQuery,
    SearchResults,
)
from graph_service.dto.episodes import episode_response_from_node
from graph_service.zep_graphiti import ZepGraphitiDep, get_fact_result_from_edge

router = APIRouter()


@router.post('/search', status_code=status.HTTP_200_OK)
async def search(query: SearchQuery, graphiti: ZepGraphitiDep):
    relevant_edges = await graphiti.search(
        group_ids=query.group_ids,
        query=query.query,
        num_results=query.max_facts,
    )
    facts = [get_fact_result_from_edge(edge) for edge in relevant_edges]
    return SearchResults(
        facts=facts,
    )


@router.get('/entity-edge/{uuid}', status_code=status.HTTP_200_OK)
async def get_entity_edge(uuid: str, graphiti: ZepGraphitiDep):
    entity_edge = await graphiti.get_entity_edge(uuid)
    return get_fact_result_from_edge(entity_edge)


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
    result = await graphiti.search(
        group_ids=[request.group_id],
        query=combined_query,
        num_results=request.max_facts,
    )
    facts = [get_fact_result_from_edge(edge) for edge in result]
    return GetMemoryResponse(facts=facts)


def compose_query_from_messages(messages: list[Message]):
    combined_query = ''
    for message in messages:
        combined_query += f'{message.role_type or ""}({message.role or ""}): {message.content}\n'
    return combined_query
