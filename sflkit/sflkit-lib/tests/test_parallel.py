import os
import shutil
import subprocess
import threading
import unittest

from sflkitlib.events.event import LineEvent, load_next_event, DefEvent

TEST_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_PARALLEL_DIR = os.path.join(TEST_DIR, "example")
TESTS = "tests.test_example"


class ParallelTest(unittest.TestCase):

    @staticmethod
    def load_events(path, events_mapping):
        events = []
        with open(path, "rb") as f:
            while f.peek(1):
                event = load_next_event(f, events_mapping, with_thread_id=True)
                events.append(event)
        return events

    def remove_files(self, file):
        path = os.path.join(TEST_PARALLEL_DIR, file)
        if os.path.exists(path):
            os.remove(path)

    def tearDown(self):
        self.remove_files("events_21345")
        self.remove_files("events_32106")
        self.remove_files("events_67")
        self.remove_files("ids_21345.txt")
        self.remove_files("ids_32106.txt")
        self.remove_files("ids_67.txt")

    def test_example(self):
        environ = os.environ.copy()
        environ["EVENTS_THREADS"] = "1"
        environ_1 = environ.copy()
        environ_1["EVENTS_PATH"] = os.path.join(TEST_PARALLEL_DIR, "events_21345")
        subprocess.run(
            [
                "python",
                "-m",
                "unittest",
                TESTS + ".ExampleTests.test_21345",
            ],
            env=environ_1,
            cwd=TEST_PARALLEL_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        environ_2 = environ.copy()
        environ_2["EVENTS_PATH"] = os.path.join(TEST_PARALLEL_DIR, "events_32106")
        subprocess.run(
            [
                "python",
                "-m",
                "unittest",
                TESTS + ".ExampleTests.test_32106",
            ],
            env=environ_2,
            cwd=TEST_PARALLEL_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        environ_3 = environ.copy()
        environ_3["EVENTS_PATH"] = os.path.join(TEST_PARALLEL_DIR, "events_67")
        subprocess.run(
            [
                "python",
                "-m",
                "unittest",
                TESTS + ".ExampleTests.test_67",
            ],
            env=environ_3,
            cwd=TEST_PARALLEL_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # load events
        events_mapping = {
            1: LineEvent("example.py", 1, 1),
            2: LineEvent("example.py", 2, 2),
            3: LineEvent("example.py", 3, 3),
            4: LineEvent("example.py", 4, 4),
            5: DefEvent("example.py", 5, 5, var="n"),
        }

        all_events_21345 = self.load_events(
            os.path.join(TEST_PARALLEL_DIR, "events_21345"), events_mapping
        )
        all_events_32106 = self.load_events(
            os.path.join(TEST_PARALLEL_DIR, "events_32106"), events_mapping
        )
        all_events_67 = self.load_events(
            os.path.join(TEST_PARALLEL_DIR, "events_67"), events_mapping
        )

        self.assertTrue(len(all_events_21345) > 0)
        self.assertTrue(len(all_events_32106) > 0)
        self.assertTrue(len(all_events_67) > 0)

        # Get thread ids
        thread_ids_21345 = set(event.thread_id for event in all_events_21345)
        thread_ids_32106 = set(event.thread_id for event in all_events_32106)
        thread_ids_67 = set(event.thread_id for event in all_events_67)

        self.assertEqual(thread_ids_21345, {0, 1, 2, 3, 4})
        self.assertEqual(thread_ids_32106, {0, 1, 2})
        self.assertEqual(thread_ids_67, {0, 1})

        # Sort events by thread id
        events_by_thread_21345 = {}
        for event in all_events_21345:
            events_by_thread_21345.setdefault(event.thread_id, []).append(event)
        events_by_thread_32106 = {}
        for event in all_events_32106:
            events_by_thread_32106.setdefault(event.thread_id, []).append(event)
        events_by_thread_67 = {}
        for event in all_events_67:
            events_by_thread_67.setdefault(event.thread_id, []).append(event)

        # first line 2
        self.assertIsInstance(events_by_thread_21345[0][0], LineEvent)
        self.assertIsInstance(events_by_thread_32106[0][0], LineEvent)
        self.assertIsInstance(events_by_thread_67[0][0], LineEvent)
        self.assertEqual(
            events_by_thread_21345[0][0].line,
            2,
        )
        self.assertEqual(
            events_by_thread_32106[0][0].line,
            2,
        )
        self.assertEqual(
            events_by_thread_67[0][0].line,
            2,
        )
        # second def 5
        self.assertIsInstance(events_by_thread_21345[0][1], DefEvent)
        self.assertIsInstance(events_by_thread_32106[0][1], DefEvent)
        self.assertIsInstance(events_by_thread_67[0][1], DefEvent)
        self.assertEqual(
            events_by_thread_21345[0][1].line,
            5,
        )
        self.assertEqual(
            events_by_thread_32106[0][1].line,
            5,
        )
        self.assertEqual(
            events_by_thread_67[0][1].line,
            5,
        )
        # third line 4
        self.assertIsInstance(events_by_thread_21345[0][2], LineEvent)
        self.assertIsInstance(events_by_thread_32106[0][2], LineEvent)
        self.assertIsInstance(events_by_thread_67[0][2], LineEvent)
        self.assertEqual(
            events_by_thread_21345[0][2].line,
            4,
        )
        self.assertEqual(
            events_by_thread_32106[0][2].line,
            4,
        )
        self.assertEqual(
            events_by_thread_67[0][2].line,
            4,
        )

        # now the threads should be line 3 followed by multiple line 1s
        for thread_id in thread_ids_21345:
            if thread_id == 0:
                continue
            events = events_by_thread_21345[thread_id]
            self.assertIsInstance(events[0], LineEvent)
            self.assertEqual(events[0].line, 3)
            for event in events[1:]:
                self.assertIsInstance(event, LineEvent)
                self.assertEqual(event.line, 1)
        for thread_id in thread_ids_32106:
            if thread_id == 0:
                continue
            events = events_by_thread_32106[thread_id]
            self.assertIsInstance(events[0], LineEvent)
            self.assertEqual(events[0].line, 3)
            for event in events[1:]:
                self.assertIsInstance(event, LineEvent)
                self.assertEqual(event.line, 1)
        for thread_id in thread_ids_67:
            if thread_id == 0:
                continue
            events = events_by_thread_67[thread_id]
            self.assertIsInstance(events[0], LineEvent)
            self.assertEqual(events[0].line, 3)
            for event in events[1:]:
                self.assertIsInstance(event, LineEvent)
                self.assertEqual(event.line, 1)
