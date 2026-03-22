from datetime import datetime

from graphiti_core.nodes import EpisodeType  # type: ignore
from graphiti_core.utils.datetime_utils import utc_now
from pydantic import BaseModel, Field

from graph_service.dto.common import Message


class AddMessagesRequest(BaseModel):
    group_id: str = Field(..., description='The group id of the messages to add')
    messages: list[Message] = Field(..., description='The messages to add')


class AddEntityNodeRequest(BaseModel):
    uuid: str = Field(..., description='The uuid of the node to add')
    group_id: str = Field(..., description='The group id of the node to add')
    name: str = Field(..., description='The name of the node to add')
    summary: str = Field(default='', description='The summary of the node to add')


class AddEpisodeRequest(BaseModel):
    group_id: str = Field(..., description='The group id of the episode to add')
    episode_body: str = Field(
        ...,
        description=(
            'Raw episode content. Use plain text for `text`, a JSON string for `json`, '
            'or a preformatted message string for `message`.'
        ),
    )
    source: EpisodeType = Field(
        default=EpisodeType.message,
        description='The native Graphiti episode source type to use for ingestion',
    )
    uuid: str | None = Field(default=None, description='Optional uuid for the episode')
    name: str = Field(default='', description='Optional episodic node name')
    source_description: str = Field(
        default='',
        description='Optional description of the upstream source for this episode',
    )
    reference_time: datetime = Field(
        default_factory=utc_now,
        description='Reference timestamp used for temporal extraction',
    )
    update_communities: bool = Field(
        default=False,
        description='Whether to update community summaries as part of episode processing',
    )
    excluded_entity_types: list[str] | None = Field(
        default=None,
        description='Optional entity type names to exclude from extraction',
    )
    previous_episode_uuids: list[str] | None = Field(
        default=None,
        description='Optional explicit previous episodes to use instead of recent retrieval',
    )
    custom_extraction_instructions: str | None = Field(
        default=None,
        description='Optional extra extraction guidance passed through to Graphiti',
    )
    saga: str | None = Field(
        default=None,
        description='Optional saga name to associate this episode with',
    )
    saga_previous_episode_uuid: str | None = Field(
        default=None,
        description='Optional previous saga episode uuid for ordered saga ingestion',
    )
