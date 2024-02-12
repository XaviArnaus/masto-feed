from typing import Protocol, runtime_checkable
from pyxavi.config import Config
from mastofeed.lib.queue_post import QueuePost


@runtime_checkable
class ParserProtocol(Protocol):

    def __init__(self, config: Config) -> None:
        """Initializing the class"""

    def get_sources(self) -> dict:
        """Gets each source and all related parameters by name"""

    def get_raw_content_for_source(self, source: str) -> list[QueuePost]:
        """Gets the data from the source"""

    def is_id_already_seen_for_source(self, source: str, id: any) -> bool:
        """Returns True if the ID is already registered in the state by the given source"""

    def set_ids_as_seen_for_source(self, source: str, list_of_ids: list) -> bool:
        """Performs the saving of the seen state"""

    def post_process_for_source(self, source: str, posts: list[QueuePost]) -> list[QueuePost]:
        """Proccesses a list of posts and return a new one"""

    def parse_media(self, post: QueuePost) -> None:
        """
        Downloads the media attached to the content, if exists

        If so, will update the referenced post's media field
        Otherwise does nothing.

        This method not necessarily downloads the media. The Publisher
        can do that. It is left to the parser to decide
        """

    def format_post_for_source(self, source: str, post: QueuePost) -> None:
        """Apply a format to a single post"""
