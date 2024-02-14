from __future__ import annotations
from pyxavi.queue_stack import QueueItemProtocol
from datetime import datetime
import logging


class QueuePost(QueueItemProtocol):
    """Represents one item to post via Queue"""

    id: any = None
    group: str = None
    summary: str = None
    text: str = None
    raw_content: any = None
    action: QueuePostAction = None
    language: str = None
    media: list[QueuePostMedia] = None
    published_at: datetime = None

    def __init__(
        self,
        id: any = None,
        group: str = None,
        summary: str = None,
        text: str = None,
        raw_content: any = None,
        raw_combined_content: str = None,
        action: QueuePostAction = None,
        language: str = None,
        media: list[QueuePostMedia] = None,
        published_at: datetime = None,
    ) -> None:

        self.id = id
        self.group = group
        self.summary = summary
        self.text = text
        self.raw_content = raw_content
        self.raw_combined_content = raw_combined_content
        self.action = action if action is not None else QueuePostAction.NEW
        self.language = language
        self.media = media
        self.published_at = published_at

    def to_dict(self) -> dict:
        # Attention: raw_content and raw_combined_body
        #   won't be part of the to/from dict.
        #   Be careful when saving to / loading from file
        return {
            "id": self.id,
            "group": self.group,
            "summary": self.summary,
            "text": self.text,
            "action": str(self.action),
            "language": self.language,
            "media": list(map(lambda x: x.to_dict(), self.media)) if self.media else None,
            "published_at": datetime.timestamp(self.published_at)
            if self.published_at is not None else None,
        }

    @staticmethod
    def from_dict(dictionary: dict) -> QueuePost:
        # Attention: raw_content and raw_combined_body
        #   won't be part of the to/from dict.
        #   Be careful when saving to / loading from file
        return QueuePost(
            id=dictionary["id"] if "id" in dictionary else None,
            group=dictionary["group"] if "group" in dictionary else None,
            summary=dictionary["summary"] if "summary" in dictionary else None,
            text=dictionary["text"] if "text" in dictionary else None,
            language=dictionary["language"] if "language" in dictionary else None,
            action=QueuePostAction.valid_or_raise(dictionary["action"])
            if "action" in dictionary else None,
            media=list(map(lambda x: QueuePostMedia.from_dict(x), dictionary["media"]))
            if "media" in dictionary and dictionary["media"] else None,
            published_at=datetime.fromtimestamp(dictionary["published_at"])
        )

    def sort_value(self, param: any = None) -> any:
        if not isinstance(self.published_at, datetime):
            logging.getLogger().error(self.to_dict())
        return self.published_at

    def unique_value(self, param: any = None) -> any:
        return self.id


class QueuePostAction:
    """Enum for available actions to perform"""

    NEW = "new"

    def valid_or_raise(value: str) -> QueuePostAction:
        valid_items = list(map(lambda x: str(x), QueuePostAction.priority()))

        if value not in valid_items:
            raise RuntimeError(f"Value [{value}] is not a valid MessageType")

        return value

    def priority() -> list:
        return [QueuePostAction.NEW]


class QueuePostMedia:
    """Media already downloaded and ready to be posted"""

    url: str = None
    alt_text: str = None
    path: str = None
    mime_type: str = None

    def __init__(
        self,
        url: str = None,
        alt_text: str = None,
        path: str = None,
        mime_type: str = None,
    ) -> None:

        self.url = url
        self.alt_text = alt_text
        self.path = path
        self.mime_type = mime_type

        if self.url is None and self.path is None:
            raise RuntimeError("The URL and PATH can't be None at the same time")

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "alt_text": self.alt_text,
            "path": self.path,
            "mime_type": self.mime_type,
        }

    def from_dict(media_dict: dict) -> QueuePostMedia:
        return QueuePostMedia(
            media_dict["url"] if "url" in media_dict else None,
            media_dict["alt_text"] if "alt_text" in media_dict else None,
            media_dict["path"] if "path" in media_dict else None,
            media_dict["mime_type"] if "mime_type" in media_dict else None,
        )
