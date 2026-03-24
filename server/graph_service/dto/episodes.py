from datetime import datetime, timezone

from graphiti_core.nodes import EpisodeType, EpisodicNode  # type: ignore
from pydantic import BaseModel, Field


class EpisodeResponse(BaseModel):
    uuid: str = Field(..., description='The episode uuid')
    name: str = Field(..., description='The episode name')
    group_id: str = Field(..., description='The episode group id')
    episode_body: str = Field(..., description='The raw episode body stored by Graphiti')
    source: EpisodeType = Field(..., description='The native Graphiti episode source')
    source_description: str = Field(..., description='The upstream source description')
    reference_time: datetime = Field(..., description='The episode reference timestamp')

    class Config:
        json_encoders = {datetime: lambda v: v.astimezone(timezone.utc).isoformat()}


class AddEpisodeResponse(BaseModel):
    episode_id: str = Field(..., description='Stable REST identifier for the newly written episode')
    episode: EpisodeResponse = Field(..., description='Minimal episode payload for immediate read-after-write')


def episode_response_from_node(episode: EpisodicNode) -> EpisodeResponse:
    return EpisodeResponse(
        uuid=episode.uuid,
        name=episode.name,
        group_id=episode.group_id,
        episode_body=episode.content,
        source=episode.source,
        source_description=episode.source_description,
        reference_time=episode.valid_at,
    )
