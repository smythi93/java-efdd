import sys


sys.path = sys.path[1:] + sys.path[:1]
import atexit
import os
import pickle
import threading
from typing import Any

sys.path = sys.path[-1:] + sys.path[:-1]

from sflkitlib.events import codec

_event_path_file = open(os.getenv("EVENTS_PATH", default="EVENTS_PATH"), "wb")
_threading = int(os.getenv("EVENTS_THREADS", default="0"))

_thread_counter = 0
_thread_counter_lock = threading.Lock()
_thread_ids = {}


def _get_thread_id():
    """Get the current thread ID if threading is enabled, otherwise None.

    Uses threading.get_ident() instead of os.getpid() because:
    - threading.get_ident() distinguishes between different threads in the same process
    - os.getpid() returns the same value for all threads in a process
    - This is needed to track events from concurrent threads properly

    Returns:
        int or None: Thread identifier if threading is enabled, None otherwise
    """
    if _threading:
        thread = threading.current_thread()
        if thread not in _thread_ids:
            with _thread_counter_lock:
                global _thread_counter
                _thread_ids[thread] = _thread_counter
                _thread_counter += 1
        return _thread_ids[thread]
    return None


def reset():
    # noinspection PyBroadException
    try:
        dump_events()
    except:
        pass
    global _event_path_file
    _event_path_file = open(os.getenv("EVENTS_PATH", default="EVENTS_PATH"), "wb")


def get_id(x: Any):
    try:
        return id(x)
    except (AttributeError, TypeError):
        return None


def get_type(x: Any):
    try:
        return type(x)
    except (AttributeError, TypeError):
        return None


def dump_events():
    try:
        _event_path_file.flush()
        _event_path_file.close()
    except:
        pass


def write(encoded_event: bytes):
    global _event_path_file
    try:
        _event_path_file.write(encoded_event)
    except ValueError:
        pass


atexit.register(dump_events)


def add_line_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))


def add_branch_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))


def add_def_event(event_id: int, var_id: int, value: Any, type_: type):
    if var_id is not None:
        if type_ in [int, float, complex, str, bytes, bytearray, bool] or value is None:
            write(
                codec.encode_def_event(
                    event_id,
                    var_id,
                    pickle.dumps(value),
                    type_.__name__,
                    _get_thread_id(),
                )
            )
        else:
            write(
                codec.encode_def_event(
                    event_id,
                    var_id,
                    pickle.dumps(None),
                    f"{type_.__module__}.{type_.__name__}",
                    _get_thread_id(),
                )
            )


def add_function_enter_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))


def add_function_exit_event(
    event_id: int,
    return_value: Any,
    type_: type,
):
    if (
        type_ in [int, float, complex, str, bytes, bytearray, bool]
        or return_value is None
    ):
        write(
            codec.encode_function_exit_event(
                event_id,
                pickle.dumps(return_value),
                type_.__name__,
                _get_thread_id(),
            )
        )
    else:
        # noinspection PyBroadException
        try:
            write(
                codec.encode_function_exit_event(
                    event_id,
                    pickle.dumps(bool(return_value)),
                    f"{type_.__module__}.{type_.__name__}",
                    _get_thread_id(),
                )
            )
        except:
            write(
                codec.encode_function_exit_event(
                    event_id,
                    pickle.dumps(None),
                    f"{type_.__module__}.{type_.__name__}",
                    _get_thread_id(),
                )
            )


def add_function_error_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))


def add_condition_event(event_id: int, value: Any):
    if value:
        write(codec.encode_condition_event(event_id, True, _get_thread_id()))
    else:
        write(codec.encode_condition_event(event_id, False, _get_thread_id()))


def add_loop_begin_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))


def add_loop_hit_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))


def add_loop_end_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))


def add_use_event(event_id: int, var_id: int):
    if var_id is not None:
        write(codec.encode_use_event(event_id, var_id, _get_thread_id()))


def add_len_event(event_id: int, var_id: int, length: int):
    if var_id is not None:
        write(codec.encode_len_event(event_id, var_id, length, _get_thread_id()))


def add_test_start_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))


def add_test_end_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))


def add_test_line_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))


def add_test_def_event(event_id: int, var_id: int):
    if var_id is not None:
        write(codec.encode_base_def_event(event_id, var_id, _get_thread_id()))


def add_test_use_event(event_id: int, var_id: int):
    if var_id is not None:
        write(codec.encode_use_event(event_id, var_id, _get_thread_id()))


def add_test_assert_event(event_id: int):
    write(codec.encode_event(event_id, _get_thread_id()))
