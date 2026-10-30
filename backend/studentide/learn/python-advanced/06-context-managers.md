---
title: Context managers
summary: How with works, and writing your own with __enter__/__exit__ or contextlib.
---
`with open(...) as f:` guarantees the file is closed, even if an error happens inside the block. Any object can do this: a **context manager** has an `__enter__` method (run at the start of the block) and an `__exit__` method (run at the end, whatever happens).

```python
class Timer:
    def __enter__(self):
        import time
        self.start = time.perf_counter()
        return self                      # this is what "as t" gets

    def __exit__(self, exc_type, exc, tb):
        import time
        self.seconds = time.perf_counter() - self.start
        print(f"block took {self.seconds:.4f} s")
        return False                     # don't swallow exceptions

with Timer() as t:
    total = sum(i * i for i in range(200_000))
print(total)
```

The `contextlib` module makes this shorter: write a generator that does the setup, `yield`s once, and does the clean-up after.

```python
from contextlib import contextmanager

@contextmanager
def indented(level):
    print("  " * level + "{")
    try:
        yield level + 1
    finally:
        print("  " * level + "}")        # runs even if the block raises

with indented(0) as lvl:
    print("  " * lvl + "inside")
    with indented(lvl) as lvl2:
        print("  " * lvl2 + "deeper")
```

- `__exit__` gets the exception (if any). Returning `True` from it would *suppress* the exception: rarely what you want.
- `contextlib.suppress(FileNotFoundError)` is a ready-made context manager that ignores one kind of error.
- Typical uses: files, locks, database transactions, temporary changes that must be undone.

Things to try:

1. Raise an exception inside `with Timer():`. Does the timing still print?
2. Make `__exit__` return `True` and raise inside the block again. What changed?
3. Write `@contextmanager def changed_dir(path)` that changes directory and always changes back.

## Exercise

Write a context manager `Transaction` for a list-based "account log": on enter it remembers a copy of the list; if the block raises an exception, on exit it puts the list back exactly as it was and swallows the error, printing `rolled back`; if the block finishes normally it prints `committed`. The program runs a few transactions from the input.

```input
3
add 5 add 7
add 1 fail
add 2
```

```python starter
class Transaction:
    def __init__(self, log):
        self.log = log


log = []
for _ in range(int(input())):
    words = input().split()
    with Transaction(log):
        for i in range(0, len(words), 2):
            if words[i] == "fail":
                raise RuntimeError("payment failed")
            log.append(int(words[i + 1]))
print(log)
```

```python solution
class Transaction:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        self.saved = list(self.log)
        return self.log

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            print("committed")
            return False
        self.log[:] = self.saved
        print("rolled back")
        return True


log = []
for _ in range(int(input())):
    words = input().split()
    with Transaction(log):
        for i in range(0, len(words), 2):
            if words[i] == "fail":
                raise RuntimeError("payment failed")
            log.append(int(words[i + 1]))
print(log)
```

```tests
{"name": "example", "stdin": "3\nadd 5 add 7\nadd 1 fail\nadd 2\n", "expected": "committed\nrolled back\ncommitted\n[5, 7, 2]"}
{"name": "all fail", "stdin": "1\nfail\n", "expected": "rolled back\n[]"}
```
