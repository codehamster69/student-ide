---
title: Arguments and scope
summary: Keyword arguments, *args and **kwargs, unpacking, local and global names, nonlocal, and the mutable default trap.
---
Arguments can be passed by position or by name. Named (**keyword**) arguments can come in any order and make calls easier to read. A parameter after `*` must be passed by name.

```python
def greet(name, greeting="Hello", *, shout=False):
    text = f"{greeting}, {name}!"
    return text.upper() if shout else text

print(greet("Asha"))
print(greet(greeting="Hi", name="Ravi"))
print(greet("Dev", shout=True))
```

`*args` collects any extra positional arguments into a tuple, and `**kwargs` collects extra keyword arguments into a dict. The same stars **unpack** a list or dict into a call.

```python
def describe(title, *args, **kwargs):
    print(title, args, kwargs)

describe("order", 3, 4, colour="red", size="M")
nums = [3, 1, 2]
print(max(*nums), sorted(nums))
options = {"sep": " | ", "end": "!\n"}
print("a", "b", "c", **options)
```

**Scope**: a name assigned inside a function is local to it. Reading a name the function doesn't assign finds the outer one. To *assign* to a module-level name from inside a function you need `global`, and for the enclosing function's name, `nonlocal`. Both are best kept rare: returning values is clearer.

```python
count = 0

def bump():
    global count
    count += 1

def make_counter():
    n = 0
    def step():
        nonlocal n
        n += 1
        return n
    return step

bump(); bump()
c = make_counter()
print(count, c(), c(), c())
```

The **mutable default trap**: a default value is created once, when the function is defined, not on each call. A list default is shared by every call that uses it.

```python
def add_bad(item, bag=[]):
    bag.append(item)
    return bag

def add_good(item, bag=None):
    if bag is None:
        bag = []
    bag.append(item)
    return bag

print(add_bad(1), add_bad(2))     # [1, 2] [1, 2]: the same list!
print(add_good(1), add_good(2))   # [1] [2]
```

Things to try:

1. Remove `global count` and run. Read the error.
2. Call `greet("Dev", "Yo", True)`. Why is it rejected?
3. Print `add_bad.__defaults__` after a few calls.

## Exercise

Write `summary(*nums, places=1)`, which returns a string with the count, the smallest, the largest and the average of its arguments, the average rounded to `places` decimals, like `count=3 min=2 max=9 avg=5.0`. With no numbers it returns `count=0`. The given code reads the numbers and an optional `places` value.

```input
4 2 9
1
```

```python starter
def summary(*nums, places=1):
    return ""

nums = list(map(int, input().split()))
places = input().strip()
if places:
    print(summary(*nums, places=int(places)))
else:
    print(summary(*nums))
```

```python solution
def summary(*nums, places=1):
    if not nums:
        return "count=0"
    avg = sum(nums) / len(nums)
    return f"count={len(nums)} min={min(nums)} max={max(nums)} avg={avg:.{places}f}"

nums = list(map(int, input().split()))
places = input().strip()
if places:
    print(summary(*nums, places=int(places)))
else:
    print(summary(*nums))
```

```tests
{"name": "example", "stdin": "4 2 9\n1\n", "expected": "count=3 min=2 max=9 avg=5.0"}
{"name": "places 3", "stdin": "1 2\n3\n", "expected": "count=2 min=1 max=2 avg=1.500"}
{"name": "default places", "stdin": "10\n\n", "expected": "count=1 min=10 max=10 avg=10.0"}
{"name": "empty", "stdin": "\n2\n", "expected": "count=0", "hidden": true}
```
