---
title: Recursion and memoisation
summary: Solve a problem from smaller copies of itself, and remember answers so it stays fast.
---
A recursive function calls itself on a smaller input until it reaches a base case. Some problems are naturally recursive, like walking nested lists:

```python
def flatten(items):
    out = []
    for x in items:
        if isinstance(x, list):
            out.extend(flatten(x))     # a smaller copy of the same problem
        else:
            out.append(x)
    return out

print(flatten([1, [2, [3, 4]], [], 5]))
```

Plain recursion can repeat the same work again and again. `fib(30)` written naively calls `fib(2)` more than 500,000 times. **Memoisation** stores each answer the first time and reuses it. `functools.lru_cache` (or `cache`) does it with one line:

```python
from functools import lru_cache
import time

def slow_fib(n):
    return n if n < 2 else slow_fib(n - 1) + slow_fib(n - 2)

@lru_cache(maxsize=None)
def fast_fib(n):
    return n if n < 2 else fast_fib(n - 1) + fast_fib(n - 2)

t = time.perf_counter(); print(slow_fib(27), f"{time.perf_counter() - t:.2f} s")
t = time.perf_counter(); print(fast_fib(27), f"{time.perf_counter() - t:.5f} s")
print(fast_fib(300))     # instant, and Python's ints never overflow
```

- Python stops very deep recursion (about 1000 levels) with `RecursionError`. Memoised or not, a loop is better for very deep problems.
- This "remember sub-answers" idea is the heart of **dynamic programming**.

Things to try:

1. Remove `@lru_cache` from `fast_fib` and run `fast_fib(35)`. (The runner stops it after a few seconds.)
2. Write `power_set(s)` that returns every subset of a list, recursively.
3. Call `slow_fib(2000)` and read the error.

## Exercise

A staircase has `n` steps. You can climb 1, 2 or 3 steps at a time. Write `ways(n)`, the number of different ways to reach the top (`ways(0) = 1`: the empty climb). It must be fast for `n` up to 500, so memoise it. At 500 the recursion goes deeper than Python's default limit: add `sys.setrecursionlimit(5000)`, or fill a list from the bottom up instead.

```input
4
```

```python starter
from functools import lru_cache


def ways(n):
    return 0


print(ways(int(input())))
```

```python solution
import sys
from functools import lru_cache

sys.setrecursionlimit(5000)


@lru_cache(maxsize=None)
def ways(n):
    if n < 0:
        return 0
    if n == 0:
        return 1
    return ways(n - 1) + ways(n - 2) + ways(n - 3)


print(ways(int(input())))
```

```tests
{"name": "4 steps", "stdin": "4\n", "expected": "7"}
{"name": "1 step", "stdin": "1\n", "expected": "1"}
{"name": "30 steps", "stdin": "30\n", "expected": "53798080"}
{"name": "500 steps", "stdin": "500\n", "expected": "1306186569702186634983475450062372018715120191391192207156664343051610913971927959744519676992404852130396504615663042713312314219527", "hidden": true}
```
