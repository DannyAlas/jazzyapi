import datetime
import json
import re
import uuid
from typing import Literal, TypeVar, Union

import pydantic
from typing_extensions import Literal


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, str):
            # unicode for emoji
            return obj.encode("unicode_escape").decode("utf-8")
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


class JSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        for key, value in obj.items():
            if isinstance(value, str):
                try:
                    obj[key] = datetime.datetime.fromisoformat(value)
                except ValueError:
                    pass
        return obj


# WATCHING {"platform":"twitch","id":"canniny"}
class Watching(pydantic.BaseModel):
    platform: str
    id: str


# {"id":184519,"nick":"SallyRoss","roles":["USER"],"features":[],"createdDate":"2023-05-01T21:55:38Z","watching":{"platform":"youtube","id":"IXDp_dyQ4sA"}}
class User(pydantic.BaseModel):
    id: int
    nick: str
    roles: list[str]
    features: list[str]
    createdDate: datetime.datetime
    watching: Union[Watching, None]

    @pydantic.field_validator("watching", mode="before")
    def convert_watching(cls, v):
        if v is not None:
            return Watching(**v)
        return None


# MSG {"id":76796,"nick":"PimpMyGloin","roles":["USER"],"features":[],"createdDate":"2018-02-14T03:28:02Z","watching":{"platform":"twitch","id":"canniny"},"timestamp":1706393023527,"data":"diidnt Kelly_Jean call this girl garbage four days ago? OMEGALUL"}
class Message(User):
    timestamp: int
    data: str


# QUIT {"id":136726,"nick":"Synthetica","roles":["USER"],"features":[],"createdDate":"2021-08-18T16:07:16Z","watching":null,"timestamp":1706393023149}
class Quit(User):
    timestamp: int


# JOIN {"id":90792,"nick":"EMPIREFAN","roles":["USER","SUBSCRIBER"],"features":[],"createdDate":"2019-02-02T21:35:23Z","watching":null,"timestamp":1706393020104}
class Join(User):
    timestamp: int


class MessageDB(Message):
    uid: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    ttl: int


# duration is int followed by m, h, d, or w
DurationT = TypeVar("DurationT", bound=str)


class Duration(str):
    """Duration is an int followed by m, h, d, or w

    Examples
    --------
    >>> Duration("30m")
    "30m"
    >>> Duration("5m")
    "5m"
    """

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: DurationT, val_info: pydantic.ValidationInfo) -> DurationT:
        if not isinstance(v, str):
            raise TypeError("string required")
        if not re.match(r"^\d+[smhdw]$", v):
            raise ValueError(f"Provided duration `{v}` is not valid")
        return v

    @classmethod
    def to_datetime(cls, v: DurationT) -> datetime.timedelta:
        """Converts a Duration to a datetime.timedelta

        Parameters
        ----------
        v : DurationT
            The duration to convert

        Returns
        -------
        datetime.timedelta
            The converted duration
        """
        if v.endswith("m"):
            return datetime.timedelta(minutes=int(v[:-1]))
        elif v.endswith("h"):
            return datetime.timedelta(hours=int(v[:-1]))
        elif v.endswith("d"):
            return datetime.timedelta(days=int(v[:-1]))
        elif v.endswith("w"):
            return datetime.timedelta(weeks=int(v[:-1]))
        else:
            raise ValueError("duration must be int followed by m, h, d, or w")


class Phrase(pydantic.BaseModel):
    uid: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    time: datetime.datetime
    username: str
    phrase: str
    duration: Union[Duration, None]
    type: Literal["mute", "ban"]

    @pydantic.validator("duration", pre=True)
    def validate_duration(cls, v):
        if v == "":
            return None
        return v

    def json_dump(self):
        return {
            "uid": str(self.uid),
            "time": str(self.time.isoformat()),
            "username": self.username,
            "phrase": self.phrase,
            "duration": self.duration,
            "type": self.type,
        }


class Command(pydantic.BaseModel):
    type: Literal["addban", "addmute", "delban", "delmute"]


class EmbedInfo(pydantic.BaseModel):
    uid: uuid.UUID = pydantic.Field(default_factory=uuid.uuid4)
    channel: str
    platform: str
    watchers: int
    last_chat_time: datetime.datetime = datetime.datetime.now()
    last_info_update_time: datetime.datetime = datetime.datetime.now()
    title: str = ""
    type: Literal["live", "video", "clip", "offline", "unknown"] = "unknown"

    def json_dump(self):
        return {
            "uid": str(self.uid),
            "channel": self.channel,
            "platform": self.platform,
            "watchers": self.watchers,
            "last_chat_time": str(self.last_chat_time.isoformat()),
            "last_info_update_time": str(self.last_info_update_time.isoformat()),
            "title": self.title,
            "type": self.type,
        }
