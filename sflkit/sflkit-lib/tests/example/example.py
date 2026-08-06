import threading
import sflkitlib.lib


def factorial(n):
    """Calculate factorial. BUG: Returns 0 for n=0 instead of 1."""
    sflkitlib.lib.add_line_event(1)
    if n <= 0:
        result = 0
    else:
        result = 1
        for i in range(2, n + 1):
            result *= i
    return result


def compute_parallel(numbers, num_threads=2):
    """
    Compute factorials in parallel using threads.

    Args:
        numbers: List of numbers to compute factorials for
        num_threads: Number of threads to use

    Returns:
        Dictionary mapping each number to its factorial
    """
    sflkitlib.lib.add_line_event(2)
    results = {}
    lock = threading.Lock()

    def worker(nums):
        sflkitlib.lib.add_line_event(3)
        for n in nums:
            fact = factorial(n)
            with lock:
                results[n] = fact

    chunk_size = len(numbers) // num_threads
    threads = []

    for i in range(num_threads):
        start = i * chunk_size
        end = start + chunk_size if i < num_threads - 1 else len(numbers)
        t = threading.Thread(target=worker, args=(numbers[start:end],))
        threads.append(t)
        t.start()

    sflkitlib.lib.add_def_event(5, id(threads), 0, int)

    for t in threads:
        t.join()

    sflkitlib.lib.add_line_event(4)
    return [results[n] for n in numbers]
