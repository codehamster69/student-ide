---
title: Functions as values and decorators
summary: Functions that take and return functions, closures, and @decorators.
---
In Python a function is a value like any other: you can store it, pass it, and return it from another function. A function defined inside another one remembers the variables around it (a **closure**):

```python
def make_multiplier(k):
    def multiply(x):
        return x * k          # remembers k
    return multiply

double, triple = make_multiplier(2), make_multiplier(3)
print(double(5), triple(5))
print(list(map(double, [1, 2, 3])))
```

A **decorator** is a function that takes a function and returns a new one that wraps it. `@name` above a `def` applies it:

```python
import functools
import time

def timed(func):
    @functools.wraps(func)            # keep the original name and docstring
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"{func.__name__} took {time.perf_counter() - start:.4f} s")
        return result
    return wrapper

@timed                                # same as: slow_sum = timed(slow_sum)
def slow_sum(n):
    return sum(range(n))

print(slow_sum(1_000_000))
```

- `*args` collects positional arguments into a tuple and `**kwargs` keyword arguments into a dictionary, so the wrapper works for any function.
- Decorators are used for timing, logging, caching, checking permissions and retrying.

Things to try:

1. Write a decorator `shout` that upper-cases whatever string the function returns.
2. Stack two decorators on one function. Which runs first?
3. Write a decorator that takes an argument: `@repeat(3)` runs the function three times (you need one more level of nesting).

## Exercise

Write a decorator `count_calls` that counts how many times the decorated function is called, keeping the count in an attribute `calls` on the wrapper. The program decorates a recursive Fibonacci function, so every recursive call is counted too.

```input
10
```

```python starter
import functools


def count_calls(func):
    return func


@count_calls
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)


n = int(input())
print(fib(n))
print("calls", fib.calls)
```

```python solution
import functools


def count_calls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.calls += 1
        return func(*args, **kwargs)
    wrapper.calls = 0
    return wrapper


@count_calls
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)


n = int(input())
print(fib(n))
print("calls", fib.calls)
```

```tests
{"name": "fib(10)", "stdin": "10\n", "expected": "55\ncalls 177"}
{"name": "fib(1)", "stdin": "1\n", "expected": "1\ncalls 1"}
{"name": "fib(15)", "stdin": "15\n", "expected": "610\ncalls 1973", "hidden": true}
```
