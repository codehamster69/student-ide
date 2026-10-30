---
title: Type hints and testing your code
summary: Say what types a function expects and returns, check assumptions with assert, and write small tests.
---
**Type hints** say what types a function expects and returns. Python itself ignores them when running, but editors and checkers such as `mypy` use them to catch mistakes before you run, and they document the code for the next reader.

```python
from typing import Optional

def average(marks: list[float]) -> float:
    return sum(marks) / len(marks)

def find(names: list[str], target: str) -> Optional[int]:
    """Position of target in names, or None."""
    for i, n in enumerate(names):
        if n == target:
            return i
    return None

scores: dict[str, int] = {"Asha": 81}
print(average([70, 80]), find(["a", "b"], "b"), find([], "x"))
print(average.__annotations__)
```

Common hints: `int`, `str`, `list[int]`, `dict[str, int]`, `tuple[int, int]`, `set[str]`, `Optional[int]` (an `int` or `None`, also written `int | None`), and `Callable[[int], int]` for a function.

`assert condition, "message"` stops the program with an `AssertionError` if the condition is false. Use it to check things that must be true if your code is right, not to check user input (asserts can be switched off with `python -O`).

A **test** calls your function with known inputs and checks the outputs. Writing a few, including edge cases like an empty list, catches bugs early and tells you at once if a later change breaks something. Real projects use `unittest` or `pytest`, which find and run every `test_` function for you; the idea is the same as here:

```python
def is_palindrome(s: str) -> bool:
    cleaned = [c.lower() for c in s if c.isalnum()]
    return cleaned == cleaned[::-1]

def test_is_palindrome():
    assert is_palindrome("Racecar")
    assert is_palindrome("A man, a plan, a canal: Panama")
    assert not is_palindrome("hello")
    assert is_palindrome("")              # edge case: empty

test_is_palindrome()
print("all tests passed")
```

Things to try:

1. Call `average([])`. Add an `assert` that gives a clear message instead.
2. Call `average("abc")`. Does Python stop you? What would a type checker say?
3. Write a test that fails on purpose and read the error.

## Exercise

Write `def chunk(items: list[int], size: int) -> list[list[int]]`, which splits a list into pieces of `size` items (the last piece may be shorter), and make it `assert size > 0`. The given code reads a size and numbers and prints the chunks. If the size is not positive, it prints `bad size`.

```input
2
1 2 3 4 5
```

```python starter
def chunk(items: list[int], size: int) -> list[list[int]]:
    return [items]

size = int(input())
nums = list(map(int, input().split()))
try:
    for piece in chunk(nums, size):
        print(" ".join(map(str, piece)))
except AssertionError:
    print("bad size")
```

```python solution
def chunk(items: list[int], size: int) -> list[list[int]]:
    assert size > 0, "size must be positive"
    return [items[i:i + size] for i in range(0, len(items), size)]

size = int(input())
nums = list(map(int, input().split()))
try:
    for piece in chunk(nums, size):
        print(" ".join(map(str, piece)))
except AssertionError:
    print("bad size")
```

```tests
{"name": "example", "stdin": "2\n1 2 3 4 5\n", "expected": "1 2\n3 4\n5"}
{"name": "exact", "stdin": "3\n1 2 3 4 5 6\n", "expected": "1 2 3\n4 5 6"}
{"name": "zero", "stdin": "0\n1 2\n", "expected": "bad size"}
{"name": "big size", "stdin": "10\n7 8\n", "expected": "7 8", "hidden": true}
```
