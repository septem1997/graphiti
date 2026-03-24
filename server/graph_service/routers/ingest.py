import asyncio
from contextlib import asynccontextmanager
from functools import partial

from fastapi import APIRouter, FastAPI, status
from graphiti_core.nodes import EpisodeType  # type: ignore
from graphiti_core.utils.maintenance.graph_data_operations import clear_data  # type: ignore

from graph_service.dto import (
    AddEntityNodeRequest,
    AddEpisodeRequest,
    AddEpisodeResponse,
    AddMessagesRequest,
    Message,
    Result,
)
from graph_service.dto.episodes import episode_response_from_node
from graph_service.zep_graphiti import ZepGraphitiDep


class AsyncWorker:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.task = None

    async def worker(self):
        while True:
            try:
                print(f'Got a job: (size of remaining queue: {self.queue.qsize()})')
                job = await self.queue.get()
                await job()
            except asyncio.CancelledError:
                break

    async def start(self):
        self.task = asyncio.create_task(self.worker())

    async def stop(self):
        if self.task:
            self.task.cancel()
            await self.task
        while not self.queue.empty():
            self.queue.get_nowait()


async_worker = AsyncWorker()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await async_worker.start()
    yield
    await async_worker.stop()


router = APIRouter(lifespan=lifespan)


def get_message_episode_body(message: Message) -> str:
    return f'{message.role or ""}({message.role_type}): {message.content}'


@router.post(
    '/messages',
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Result,
    summary='Queue chat messages for asynchronous ingestion',
    description='Accepts message batches and enqueues them for sequential Graphiti processing.',
)
async def add_messages(
    request: AddMessagesRequest,
    graphiti: ZepGraphitiDep,
):
    async def add_messages_task(message: Message):
        await graphiti.add_episode(
            uuid=message.uuid,
            group_id=request.group_id,
            name=message.name,
            episode_body=get_message_episode_body(message),
            reference_time=message.timestamp,
            source=EpisodeType.message,
            source_description=message.source_description,
        )

    for message in request.messages:
        await async_worker.queue.put(partial(add_messages_task, message))

    return Result(message='Messages added to processing queue', success=True)


@router.post(
    '/episodes',
    status_code=status.HTTP_200_OK,
    response_model=AddEpisodeResponse,
    summary='Add a native Graphiti episode',
    description=(
        'Directly calls `graphiti.add_episode(...)` and supports native Graphiti episode '
        'sources `message`, `text`, and `json`.'
    ),
)
async def add_episode(
    request: AddEpisodeRequest,
    graphiti: ZepGraphitiDep,
) -> AddEpisodeResponse:
    result = await graphiti.add_episode(
        uuid=request.uuid,
        group_id=request.group_id,
        name=request.name,
        episode_body=request.episode_body,
        reference_time=request.reference_time,
        source=request.source,
        source_description=request.source_description,
        update_communities=request.update_communities,
        excluded_entity_types=request.excluded_entity_types,
        previous_episode_uuids=request.previous_episode_uuids,
        custom_extraction_instructions=request.custom_extraction_instructions,
        saga=request.saga,
        saga_previous_episode_uuid=request.saga_previous_episode_uuid,
    )
    return AddEpisodeResponse(
        episode_id=result.episode.uuid,
        episode=episode_response_from_node(result.episode),
    )


@router.post('/entity-node', status_code=status.HTTP_201_CREATED)
async def add_entity_node(
    request: AddEntityNodeRequest,
    graphiti: ZepGraphitiDep,
):
    node = await graphiti.save_entity_node(
        uuid=request.uuid,
        group_id=request.group_id,
        name=request.name,
        summary=request.summary,
    )
    return node


@router.delete('/entity-edge/{uuid}', status_code=status.HTTP_200_OK)
async def delete_entity_edge(uuid: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_entity_edge(uuid)
    return Result(message='Entity Edge deleted', success=True)


@router.delete('/group/{group_id}', status_code=status.HTTP_200_OK)
async def delete_group(group_id: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_group(group_id)
    return Result(message='Group deleted', success=True)


@router.delete('/episode/{uuid}', status_code=status.HTTP_200_OK)
async def delete_episode(uuid: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_episodic_node(uuid)
    return Result(message='Episode deleted', success=True)


@router.post('/clear', status_code=status.HTTP_200_OK)
async def clear(
    graphiti: ZepGraphitiDep,
):
    await clear_data(graphiti.driver)
    await graphiti.build_indices_and_constraints()
    return Result(message='Graph cleared', success=True)
