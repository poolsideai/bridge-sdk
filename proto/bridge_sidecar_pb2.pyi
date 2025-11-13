from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RunDetail(_message.Message):
    __slots__ = ("agent_name", "session_id")
    AGENT_NAME_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    agent_name: str
    session_id: str
    def __init__(self, agent_name: _Optional[str] = ..., session_id: _Optional[str] = ...) -> None: ...

class ContinueFrom(_message.Message):
    __slots__ = ("previous_run_detail", "continuation", "compaction")
    class NoCompactionStrategy(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class CompactionStrategy(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    PREVIOUS_RUN_DETAIL_FIELD_NUMBER: _ClassVar[int]
    CONTINUATION_FIELD_NUMBER: _ClassVar[int]
    COMPACTION_FIELD_NUMBER: _ClassVar[int]
    previous_run_detail: RunDetail
    continuation: ContinueFrom.NoCompactionStrategy
    compaction: ContinueFrom.CompactionStrategy
    def __init__(self, previous_run_detail: _Optional[_Union[RunDetail, _Mapping]] = ..., continuation: _Optional[_Union[ContinueFrom.NoCompactionStrategy, _Mapping]] = ..., compaction: _Optional[_Union[ContinueFrom.CompactionStrategy, _Mapping]] = ...) -> None: ...

class StartAgentRequest(_message.Message):
    __slots__ = ("prompt", "agent_name", "directory", "continue_from")
    PROMPT_FIELD_NUMBER: _ClassVar[int]
    AGENT_NAME_FIELD_NUMBER: _ClassVar[int]
    DIRECTORY_FIELD_NUMBER: _ClassVar[int]
    CONTINUE_FROM_FIELD_NUMBER: _ClassVar[int]
    prompt: str
    agent_name: str
    directory: str
    continue_from: ContinueFrom
    def __init__(self, prompt: _Optional[str] = ..., agent_name: _Optional[str] = ..., directory: _Optional[str] = ..., continue_from: _Optional[_Union[ContinueFrom, _Mapping]] = ...) -> None: ...

class StartAgentResponse(_message.Message):
    __slots__ = ("run_detail", "exit_result")
    RUN_DETAIL_FIELD_NUMBER: _ClassVar[int]
    EXIT_RESULT_FIELD_NUMBER: _ClassVar[int]
    run_detail: RunDetail
    exit_result: str
    def __init__(self, run_detail: _Optional[_Union[RunDetail, _Mapping]] = ..., exit_result: _Optional[str] = ...) -> None: ...
