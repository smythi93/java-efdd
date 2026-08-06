import io
import sys
from abc import abstractmethod, ABC
from typing import Any, List, Union, BinaryIO, Dict, Optional

from sflkitlib.events import EventType
from sflkitlib.events.codec import (
    encode_event,
    encode_def_event,
    encode_function_exit_event,
    encode_condition_event,
    encode_use_event,
    encode_len_event,
    ENDIAN,
    encode_base_def_event,
)

sys.path = sys.path[1:] + sys.path[:1]
import json
import pickle

sys.path = sys.path[-1:] + sys.path[:-1]


class Event(ABC):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        event_type: EventType,
        thread_id: Optional[int] = None,
    ):
        self.file = file
        self.line = line
        self.event_id = event_id
        self.thread_id = thread_id
        self.event_type = event_type

    def __hash__(self):
        return hash((self.file, self.line, self.event_id, self.event_type.value))

    def __eq__(self, other):
        if isinstance(other, Event):
            return (
                self.file == other.file
                and self.line == other.line
                and self.event_id == other.event_id
                and self.event_type == other.event_type
            )
        return False

    def __repr__(self):
        return f"{self.__class__.__name__}({self.file},{self.line},{self.event_id})"

    @abstractmethod
    def handle(self, model: Any, *args, **kwargs):
        raise NotImplementedError()

    def serialize(self):
        if self.thread_id is not None:
            return {
                "file": self.file,
                "line": self.line,
                "id": self.event_id,
                "event_type": self.event_type.value,
                "thread_id": self.thread_id,
            }
        return {
            "file": self.file,
            "line": self.line,
            "id": self.event_id,
            "event_type": self.event_type.value,
        }

    @staticmethod
    def get_byte_length(x: Union[int, float]):
        return (x.bit_length() + 7) // 8

    def dump(self) -> bytes:
        return encode_event(self.event_id, self.thread_id)

    @staticmethod
    def deserialize(s: dict):
        return None

    @abstractmethod
    def instantiate(self, *args, **kwargs):
        raise NotImplementedError


class EventEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Event):
            return o.serialize()
        else:
            return super().default(o)


class LineEvent(Event):
    def __init__(
        self, file: str, line: int, event_id: int, thread_id: Optional[int] = None
    ):
        super().__init__(file, line, event_id, EventType.LINE, thread_id)

    def handle(self, model: Any, *args, **kwargs):
        model.handle_line_event(self, *args, **kwargs)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id"])
        assert s["event_type"] == EventType.LINE.value
        if "thread_id" in s:
            return LineEvent(*[s[p] for p in ["file", "line", "id"]], s["thread_id"])
        return LineEvent(*[s[p] for p in ["file", "line", "id"]])

    def instantiate(self, thread_id: Optional[int] = None):
        return LineEvent(self.file, self.line, self.event_id, thread_id)


class BranchEvent(Event):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        then_id: int,
        else_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, EventType.BRANCH, thread_id)
        self.then_id = then_id
        self.else_id = else_id

    def handle(self, model: Any, *args, **kwargs):
        model.handle_branch_event(self, *args, **kwargs)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},{self.then_id},{self.else_id})"

    def serialize(self):
        default = super().serialize()
        default["then_id"] = self.then_id
        default["else_id"] = self.else_id
        return default

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "then_id", "else_id"])
        assert s["event_type"] == EventType.BRANCH.value
        return BranchEvent(
            *[s[p] for p in ["file", "line", "id", "then_id", "else_id"]]
        )

    def instantiate(self, thread_id: Optional[int] = None):
        return BranchEvent(
            self.file, self.line, self.event_id, self.then_id, self.else_id, thread_id
        )


class DefEvent(Event):
    def __init__(
        self,
        file,
        line: int,
        event_id: int,
        var: str,
        var_id: int = None,
        value: Any = None,
        type_: str = None,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, EventType.DEF, thread_id)
        self.var = var
        self.var_id = var_id
        self.value = value
        self.type_ = type_

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},"
            f"{self.var},{self.var_id},{self.value})"
        )

    def handle(self, model: Any, *args, **kwargs):
        model.handle_def_event(self, *args, **kwargs)

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        return default

    def dump(self):
        return encode_def_event(
            self.event_id,
            self.var_id,
            self.value,
            self.type_,
            self.thread_id,
        )

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "var"])
        assert s["event_type"] == EventType.DEF.value
        return DefEvent(*[s[p] for p in ["file", "line", "id", "var"]])

    def instantiate(
        self,
        var_id: int,
        value: Any,
        type_: str,
        thread_id: Optional[int] = None,
    ):
        return DefEvent(
            self.file,
            self.line,
            self.event_id,
            self.var,
            var_id,
            value,
            type_,
            thread_id,
        )


class FunctionEvent(Event, ABC):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        event_type: EventType,
        function: str,
        function_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, event_type, thread_id)
        self.function = function
        self.function_id = function_id

    def serialize(self):
        default = super().serialize()
        default["function"] = self.function
        default["function_id"] = self.function_id
        return default


class FunctionEnterEvent(FunctionEvent):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        function: str,
        function_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(
            file,
            line,
            event_id,
            EventType.FUNCTION_ENTER,
            function,
            function_id,
            thread_id,
        )

    def __repr__(self):
        return f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},{self.function})"

    def handle(self, model: Any, *args, **kwargs):
        model.handle_function_enter_event(self, *args, **kwargs)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "function", "function_id"])
        assert s["event_type"] == EventType.FUNCTION_ENTER.value
        return FunctionEnterEvent(
            *[s[p] for p in ["file", "line", "id", "function", "function_id"]]
        )

    def instantiate(self, thread_id: Optional[int] = None):
        return FunctionEnterEvent(
            self.file,
            self.line,
            self.event_id,
            self.function,
            self.function_id,
            thread_id,
        )


class FunctionExitEvent(FunctionEvent):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        function: str,
        function_id: int,
        tmp_var: str,
        return_value: Any = None,
        type_: str = None,
        thread_id: Optional[int] = None,
    ):
        super().__init__(
            file,
            line,
            event_id,
            EventType.FUNCTION_EXIT,
            function,
            function_id,
            thread_id,
        )
        self.tmp_var = tmp_var
        self.return_value = return_value
        self.type_ = type_

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},"
            f"{self.function},{self.return_value},{self.type_})"
        )

    def handle(self, model: Any, *args, **kwargs):
        model.handle_function_exit_event(self, *args, **kwargs)

    def dump(self):
        return encode_function_exit_event(
            self.event_id, self.return_value, self.type_, self.thread_id
        )

    def serialize(self):
        default = super().serialize()
        default["tmp_var"] = self.tmp_var
        return default

    @staticmethod
    def deserialize(s: dict):
        assert all(
            p in s for p in ["file", "line", "id", "function", "function_id", "tmp_var"]
        )
        assert s["event_type"] == EventType.FUNCTION_EXIT.value
        return FunctionExitEvent(
            *[
                s[p]
                for p in ["file", "line", "id", "function", "function_id", "tmp_var"]
            ]
        )

    def instantiate(
        self,
        return_value: Any,
        type_: str,
        thread_id: Optional[int] = None,
    ):
        return FunctionExitEvent(
            self.file,
            self.line,
            self.event_id,
            self.function,
            self.function_id,
            self.tmp_var,
            return_value,
            type_,
            thread_id,
        )


class FunctionErrorEvent(FunctionEvent):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        function: str,
        function_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(
            file,
            line,
            event_id,
            EventType.FUNCTION_ERROR,
            function,
            function_id,
            thread_id,
        )

    def __repr__(self):
        return f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},{self.function},{self.function_id})"

    def handle(self, model: Any, *args, **kwargs):
        model.handle_function_error_event(self, *args, **kwargs)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "function", "function_id"])
        assert s["event_type"] == EventType.FUNCTION_ERROR.value
        return FunctionErrorEvent(
            *[s[p] for p in ["file", "line", "id", "function", "function_id"]]
        )

    def instantiate(self, thread_id: Optional[int] = None):
        return FunctionErrorEvent(
            self.file,
            self.line,
            self.event_id,
            self.function,
            self.function_id,
            thread_id,
        )


class ConditionEvent(Event):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        condition: str,
        tmp_var: str,
        value: bool = None,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, EventType.CONDITION, thread_id)
        self.value = value
        self.tmp_var = tmp_var
        self.condition = condition

    def __repr__(self):
        return f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},{self.value},{self.condition})"

    def handle(self, model: Any, *args, **kwargs):
        model.handle_condition_event(self, *args, **kwargs)

    def serialize(self):
        default = super().serialize()
        default["condition"] = self.condition
        default["tmp_var"] = self.tmp_var
        return default

    def dump(self):
        return encode_condition_event(
            self.event_id,
            self.value,
            self.thread_id,
        )

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "condition", "tmp_var"])
        assert s["event_type"] == EventType.CONDITION.value
        return ConditionEvent(
            *[s[p] for p in ["file", "line", "id", "condition", "tmp_var"]]
        )

    def instantiate(
        self,
        value: bool,
        thread_id: Optional[int] = None,
    ):
        return ConditionEvent(
            self.file,
            self.line,
            self.event_id,
            self.condition,
            self.tmp_var,
            value,
            thread_id,
        )


class LoopEvent(Event, ABC):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        event_type: EventType,
        loop_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, event_type, thread_id)
        self.loop_id = loop_id

    def serialize(self):
        default = super().serialize()
        default["loop_id"] = self.loop_id
        return default


class LoopBeginEvent(LoopEvent):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        loop_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, EventType.LOOP_BEGIN, loop_id, thread_id)

    def handle(self, model: Any, *args, **kwargs):
        model.handle_loop_begin_event(self, *args, **kwargs)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "loop_id"])
        assert s["event_type"] == EventType.LOOP_BEGIN.value
        return LoopBeginEvent(*[s[p] for p in ["file", "line", "id", "loop_id"]])

    def instantiate(self, thread_id: Optional[int] = None):
        return LoopBeginEvent(
            self.file, self.line, self.event_id, self.loop_id, thread_id
        )


class LoopHitEvent(LoopEvent):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        loop_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, EventType.LOOP_HIT, loop_id, thread_id)

    def handle(self, model: Any, *args, **kwargs):
        model.handle_loop_hit_event(self, *args, **kwargs)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "loop_id"])
        assert s["event_type"] == EventType.LOOP_HIT.value
        return LoopHitEvent(*[s[p] for p in ["file", "line", "id", "loop_id"]])

    def instantiate(self, thread_id: Optional[int] = None):
        return LoopHitEvent(
            self.file, self.line, self.event_id, self.loop_id, thread_id
        )


class LoopEndEvent(LoopEvent):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        loop_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, EventType.LOOP_END, loop_id, thread_id)

    def handle(self, model: Any, *args, **kwargs):
        model.handle_loop_end_event(self, *args, **kwargs)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "loop_id"])
        assert s["event_type"] == EventType.LOOP_END.value
        return LoopEndEvent(*[s[p] for p in ["file", "line", "id", "loop_id"]])

    def instantiate(self, thread_id: Optional[int] = None):
        return LoopEndEvent(
            self.file, self.line, self.event_id, self.loop_id, thread_id
        )


class UseEvent(Event):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        var: str,
        var_id: int = None,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, EventType.USE, thread_id)
        self.var = var
        self.var_id = var_id

    def __repr__(self):
        return f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},{self.var},{self.var_id})"

    def handle(self, model: Any, *args, **kwargs):
        model.handle_use_event(self, *args, **kwargs)

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        return default

    def dump(self):
        return encode_use_event(self.event_id, self.var_id, self.thread_id)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "var"])
        assert s["event_type"] == EventType.USE.value
        return UseEvent(*[s[p] for p in ["file", "line", "id", "var"]])

    def instantiate(self, var_id, thread_id: Optional[int] = None):
        return UseEvent(
            self.file, self.line, self.event_id, self.var, var_id, thread_id
        )


class LenEvent(Event):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        var: str,
        var_id: int = None,
        length: int = None,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, EventType.LEN, thread_id)
        self.var = var
        self.var_id = var_id
        self.length = length

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},"
            f"{self.var},{self.var_id},{self.length})"
        )

    def handle(self, model: Any, *args, **kwargs):
        model.handle_len_event(self, *args, **kwargs)

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        return default

    def dump(self):
        return encode_len_event(
            self.event_id,
            self.var_id,
            self.length,
            self.thread_id,
        )

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "var"])
        assert s["event_type"] == EventType.LEN.value
        return LenEvent(*[s[p] for p in ["file", "line", "id", "var"]])

    def instantiate(self, var_id, length, thread_id: Optional[int] = None):
        return LenEvent(
            self.file,
            self.line,
            self.event_id,
            self.var,
            var_id,
            length,
            thread_id,
        )


class TestFunctionEvent(Event, ABC):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        event_type: EventType,
        test: str,
        test_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, event_type, thread_id)
        self.test = test
        self.test_id = test_id

    def serialize(self):
        default = super().serialize()
        default["test"] = self.test
        default["test_id"] = self.test_id
        return default


class TestStartEvent(TestFunctionEvent):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        test: str,
        test_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(
            file, line, event_id, EventType.TEST_START, test, test_id, thread_id
        )

    def __repr__(self):
        return f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},{self.test})"

    def handle(self, model: Any, *args, **kwargs):
        model.handle_test_start_event(self, *args, **kwargs)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "test", "test_id"])
        assert s["event_type"] == EventType.TEST_START.value
        return TestStartEvent(
            *[s[p] for p in ["file", "line", "id", "test", "test_id"]]
        )

    def instantiate(self, thread_id: Optional[int] = None):
        return TestStartEvent(
            self.file, self.line, self.event_id, self.test, self.test_id, thread_id
        )


class TestEndEvent(TestFunctionEvent):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        test: str,
        test_id: int,
        thread_id: Optional[int] = None,
    ):
        super().__init__(
            file, line, event_id, EventType.TEST_END, test, test_id, thread_id
        )

    def __repr__(self):
        return f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},{self.test})"

    def handle(self, model: Any, *args, **kwargs):
        model.handle_test_end_event(self, *args, **kwargs)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "test", "test_id"])
        assert s["event_type"] == EventType.TEST_END.value
        return TestEndEvent(*[s[p] for p in ["file", "line", "id", "test", "test_id"]])

    def instantiate(self, thread_id: Optional[int] = None):
        return TestEndEvent(
            self.file, self.line, self.event_id, self.test, self.test_id, thread_id
        )


class TestLineEvent(Event):
    def __init__(
        self, file: str, line: int, event_id: int, thread_id: Optional[int] = None
    ):
        super().__init__(file, line, event_id, EventType.TEST_LINE, thread_id)

    def handle(self, model: Any, *args, **kwargs):
        model.handle_test_line_event(self, *args, **kwargs)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id"])
        assert s["event_type"] == EventType.TEST_LINE.value
        return TestLineEvent(*[s[p] for p in ["file", "line", "id"]])

    def instantiate(self, thread_id: Optional[int] = None):
        return TestLineEvent(self.file, self.line, self.event_id, thread_id)


class TestDefEvent(Event):
    def __init__(
        self,
        file,
        line: int,
        event_id: int,
        var: str,
        var_id: int = None,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, EventType.TEST_DEF, thread_id)
        self.var = var
        self.var_id = var_id

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},"
            f"{self.var},{self.var_id})"
        )

    def handle(self, model: Any, *args, **kwargs):
        model.handle_test_def_event(self, *args, **kwargs)

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        return default

    def dump(self):
        return encode_base_def_event(
            self.event_id,
            self.var_id,
        )

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "var"])
        assert s["event_type"] == EventType.TEST_DEF.value
        return TestDefEvent(*[s[p] for p in ["file", "line", "id", "var"]])

    def instantiate(
        self,
        var_id: int,
        thread_id: Optional[int] = None,
    ):
        return TestDefEvent(
            self.file, self.line, self.event_id, self.var, var_id, thread_id
        )


class TestUseEvent(Event):
    def __init__(
        self,
        file: str,
        line: int,
        event_id: int,
        var: str,
        var_id: int = None,
        thread_id: Optional[int] = None,
    ):
        super().__init__(file, line, event_id, EventType.TEST_USE, thread_id)
        self.var = var
        self.var_id = var_id

    def __repr__(self):
        return f"{self.__class__.__name__}({self.file},{self.line},{self.event_id},{self.var},{self.var_id})"

    def handle(self, model: Any, *args, **kwargs):
        model.handle_test_use_event(self, *args, **kwargs)

    def serialize(self):
        default = super().serialize()
        default["var"] = self.var
        return default

    def dump(self):
        return encode_use_event(self.event_id, self.var_id)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id", "var"])
        assert s["event_type"] == EventType.TEST_USE.value
        return TestUseEvent(*[s[p] for p in ["file", "line", "id", "var"]])

    def instantiate(self, var_id, thread_id: Optional[int] = None):
        return TestUseEvent(
            self.file, self.line, self.event_id, self.var, var_id, thread_id
        )


class TestAssertEvent(Event):
    def __init__(
        self, file: str, line: int, event_id: int, thread_id: Optional[int] = None
    ):
        super().__init__(file, line, event_id, EventType.TEST_ASSERT, thread_id)

    def handle(self, model: Any, *args, **kwargs):
        model.handle_test_assert_event(self, *args, **kwargs)

    @staticmethod
    def deserialize(s: dict):
        assert all(p in s for p in ["file", "line", "id"])
        assert s["event_type"] == EventType.TEST_ASSERT.value
        return TestAssertEvent(*[s[p] for p in ["file", "line", "id"]])

    def instantiate(self, thread_id: Optional[int] = None):
        return TestAssertEvent(self.file, self.line, self.event_id, thread_id)


def serialize(event: Event):
    return event.serialize()


event_mapping = {
    EventType.LINE: LineEvent,
    EventType.BRANCH: BranchEvent,
    EventType.DEF: DefEvent,
    EventType.USE: UseEvent,
    EventType.FUNCTION_ENTER: FunctionEnterEvent,
    EventType.FUNCTION_EXIT: FunctionExitEvent,
    EventType.FUNCTION_ERROR: FunctionErrorEvent,
    EventType.LOOP_BEGIN: LoopBeginEvent,
    EventType.LOOP_HIT: LoopHitEvent,
    EventType.LOOP_END: LoopEndEvent,
    EventType.CONDITION: ConditionEvent,
    EventType.LEN: LenEvent,
    EventType.TEST_START: TestStartEvent,
    EventType.TEST_END: TestEndEvent,
    EventType.TEST_LINE: TestLineEvent,
    EventType.TEST_DEF: TestDefEvent,
    EventType.TEST_USE: TestUseEvent,
    EventType.TEST_ASSERT: TestAssertEvent,
}


def deserialize(s: dict):
    assert "event_type" in s
    type_ = EventType(s["event_type"])
    return event_mapping[type_].deserialize(s)


def dump(path: str, events: List[Event]):
    with open(path, "wb") as fp:
        for e in events:
            fp.write(e.dump())


def read_int(stream: BinaryIO, n: int, signed: bool = False) -> int:
    return int.from_bytes(stream.read(n), ENDIAN, signed=signed)


def read_len_str(stream: BinaryIO, n: int) -> str:
    length = read_int(stream, n)
    return stream.read(length).decode("utf8")


def read_len_bytes(stream: BinaryIO, n: int) -> bytes:
    length = read_int(stream, n)
    return stream.read(length)


def read_len_int(stream: BinaryIO, n: int, signed: bool = False) -> int:
    length = read_int(stream, n)
    return read_int(stream, length, signed=signed)


def load_event(
    e: bytes, base_events: Dict[int, Event], with_thread_id: bool = False
) -> Event:
    return load_next_event(io.BytesIO(e), base_events, with_thread_id)


def load_next_event(
    stream: BinaryIO, events: Dict[int, Event], with_thread_id: bool = False
) -> Event:
    test = stream.read(1)
    if not test:
        raise ValueError("empty stream")

    # Read thread_id if present
    thread_id = None
    if with_thread_id:
        thread_id = read_int(stream, int.from_bytes(test, ENDIAN))
        test = stream.read(1)
        if not test:
            raise ValueError("unexpected end of stream")

    event = events[read_int(stream, int.from_bytes(test, ENDIAN))]
    if event.event_type == EventType.DEF:
        # noinspection PyBroadException
        var_id = read_len_int(stream, 1)
        value = read_len_bytes(stream, 4)
        type_ = read_len_str(stream, 2)
        try:
            return event.instantiate(
                var_id, pickle.loads(value), type_, thread_id=thread_id
            )
        except:
            value = value.decode("utf8", errors="replace")
            if value == "True":
                return event.instantiate(var_id, True, type_, thread_id=thread_id)
            elif value == "False":
                return event.instantiate(var_id, False, type_, thread_id=thread_id)
            else:
                return event.instantiate(var_id, None, type_, thread_id=thread_id)
    elif event.event_type == EventType.USE:
        var_id = read_len_int(stream, 1)
        return event.instantiate(var_id, thread_id=thread_id)
    elif event.event_type == EventType.FUNCTION_EXIT:
        # noinspection PyBroadException
        value = read_len_bytes(stream, 4)
        type_ = read_len_str(stream, 2)
        try:
            return event.instantiate(pickle.loads(value), type_, thread_id=thread_id)
        except:
            value = value.decode("utf8", errors="replace")
            if value == "True":
                return event.instantiate(True, type_, thread_id=thread_id)
            elif value == "False":
                return event.instantiate(False, type_, thread_id=thread_id)
            else:
                return event.instantiate(None, type_, thread_id=thread_id)
    elif event.event_type == EventType.CONDITION:
        value = bool(read_int(stream, 1))
        return event.instantiate(value, thread_id=thread_id)
    elif event.event_type == EventType.LEN:
        var_id = read_len_int(stream, 1)
        length = read_len_int(stream, 1)
        return event.instantiate(var_id, length, thread_id=thread_id)
    elif event.event_type == EventType.TEST_DEF:
        var_id = read_len_int(stream, 1)
        return event.instantiate(var_id, thread_id=thread_id)
    elif event.event_type == EventType.TEST_USE:
        var_id = read_len_int(stream, 1)
        return event.instantiate(var_id, thread_id=thread_id)
    else:
        return event.instantiate(thread_id=thread_id)


def load(
    path, base_events: Dict[int, Event], with_thread_id: bool = False
) -> List[Event]:
    events = list()
    with open(path, "rb") as fp:
        while True:
            try:
                events.append(load_next_event(fp, base_events, with_thread_id))
            except:
                break
    return events


def load_json(path) -> Dict[int, Event]:
    with open(path, "r") as fp:
        events = json.load(fp)
    return {event.event_id: event for event in map(deserialize, events)}
