import io
import os
import unittest
from pathlib import Path
from typing import Dict

from sflkitlib.events import codec
from sflkitlib.events import event
from sflkitlib.events.event import Event

FILE = "main.py"
LINE = 1
ID = 0


class CodecTest(unittest.TestCase):
    def _assert(
        self,
        e: event.Event,
        dump: bytes,
        mapping: Dict[int, Event],
        with_thread_id: bool = False,
    ):
        self.assertEqual(e.dump(), dump)
        self.assertEqual(
            e, event.load_next_event(io.BytesIO(dump), mapping, with_thread_id)
        )

    def test_line(self):
        e = event.LineEvent(FILE, LINE, ID)
        dump = codec.encode_event(ID)
        self._assert(e, dump, {ID: e})

    def test_branch(self):
        e = event.BranchEvent(FILE, LINE, ID, 0, -1)
        dump = codec.encode_event(ID)
        self._assert(e, dump, {ID: e})

    def test_def(self):
        e = event.DefEvent(FILE, LINE, ID, "x", 1, 1, "int")
        dump = codec.encode_def_event(ID, 1, 1, "int")
        self._assert(e, dump, {ID: e})

    def test_function_enter(self):
        e = event.FunctionEnterEvent(FILE, LINE, ID, "main", 1)
        dump = codec.encode_event(ID)
        self._assert(e, dump, {ID: e})

    def test_function_exit(self):
        e = event.FunctionExitEvent(FILE, LINE, ID, "main", 1, "tmp", 1, "int")
        dump = codec.encode_function_exit_event(ID, 1, "int")
        self._assert(e, dump, {ID: e})

    def test_function_error(self):
        e = event.FunctionErrorEvent(FILE, LINE, ID, "main", 1)
        dump = codec.encode_event(ID)
        self._assert(e, dump, {ID: e})

    def test_condition(self):
        e = event.ConditionEvent(FILE, LINE, ID, "x < y", "tmp", False)
        dump = codec.encode_condition_event(ID, False)
        self._assert(e, dump, {ID: e})

    def test_loop_begin(self):
        e = event.LoopBeginEvent(FILE, LINE, ID, 1)
        dump = codec.encode_event(ID)
        self._assert(e, dump, {ID: e})

    def test_loop_hit(self):
        e = event.LoopHitEvent(FILE, LINE, ID, 1)
        dump = codec.encode_event(ID)
        self._assert(e, dump, {ID: e})

    def test_loop_end(self):
        e = event.LoopEndEvent(FILE, LINE, ID, 1)
        dump = codec.encode_event(ID)
        self._assert(e, dump, {ID: e})

    def test_use(self):
        e = event.UseEvent(FILE, LINE, ID, "x", 1)
        dump = codec.encode_use_event(ID, 1)
        self._assert(e, dump, {ID: e})

    def test_len(self):
        e = event.LenEvent(FILE, LINE, ID, "x", 1, 5)
        dump = codec.encode_len_event(ID, 1, 5)
        self._assert(e, dump, {ID: e})

    def test_read_multiple(self):
        e_1 = event.LineEvent(FILE, 1, 0)
        e_2 = event.LineEvent(FILE, 2, 1)
        e_3 = event.LineEvent(FILE, 3, 2)
        path = Path("tmp")
        with path.open("wb") as fp:
            fp.write(e_1.dump())
            fp.write(e_2.dump())
            fp.write(e_3.dump())
        try:
            events = event.load(path, {0: e_1, 1: e_2, 2: e_3})
            self.assertEqual(3, len(events))
            self.assertEqual(e_1, events[0])
            self.assertEqual(e_2, events[1])
            self.assertEqual(e_3, events[2])
        finally:
            os.remove(path)

    # Threading tests
    def test_line_with_thread(self):
        thread_id = 12345
        e = event.LineEvent(FILE, LINE, ID, thread_id)
        dump = codec.encode_event(ID, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_branch_with_thread(self):
        thread_id = 12345
        e = event.BranchEvent(FILE, LINE, ID, 0, -1, thread_id)
        dump = codec.encode_event(ID, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_def_with_thread(self):
        thread_id = 12345
        e = event.DefEvent(FILE, LINE, ID, "x", 1, 1, "int", thread_id)
        dump = codec.encode_def_event(ID, 1, 1, "int", thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_function_enter_with_thread(self):
        thread_id = 12345
        e = event.FunctionEnterEvent(FILE, LINE, ID, "main", 1, thread_id)
        dump = codec.encode_event(ID, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_function_exit_with_thread(self):
        thread_id = 12345
        e = event.FunctionExitEvent(
            FILE, LINE, ID, "main", 1, "tmp", 1, "int", thread_id
        )
        dump = codec.encode_function_exit_event(ID, 1, "int", thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_function_error_with_thread(self):
        thread_id = 12345
        e = event.FunctionErrorEvent(FILE, LINE, ID, "main", 1, thread_id)
        dump = codec.encode_event(ID, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_condition_with_thread(self):
        thread_id = 12345
        e = event.ConditionEvent(FILE, LINE, ID, "x < y", "tmp", False, thread_id)
        dump = codec.encode_condition_event(ID, False, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_loop_begin_with_thread(self):
        thread_id = 12345
        e = event.LoopBeginEvent(FILE, LINE, ID, 1, thread_id)
        dump = codec.encode_event(ID, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_loop_hit_with_thread(self):
        thread_id = 12345
        e = event.LoopHitEvent(FILE, LINE, ID, 1, thread_id)
        dump = codec.encode_event(ID, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_loop_end_with_thread(self):
        thread_id = 12345
        e = event.LoopEndEvent(FILE, LINE, ID, 1, thread_id)
        dump = codec.encode_event(ID, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_use_with_thread(self):
        thread_id = 12345
        e = event.UseEvent(FILE, LINE, ID, "x", 1, thread_id)
        dump = codec.encode_use_event(ID, 1, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_len_with_thread(self):
        thread_id = 12345
        e = event.LenEvent(FILE, LINE, ID, "x", 1, 5, thread_id)
        dump = codec.encode_len_event(ID, 1, 5, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)

    def test_encode_with_real_thread_id(self):
        thread_id = 8681598528
        e = event.LineEvent(FILE, LINE, ID, thread_id)
        dump = codec.encode_event(ID, thread_id)
        self._assert(e, dump, {ID: e}, with_thread_id=True)
