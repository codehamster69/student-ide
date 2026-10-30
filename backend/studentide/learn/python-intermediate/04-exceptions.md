---
title: Errors and exceptions
summary: try, except, else, finally, and raising your own errors.
---
When something goes wrong, Python **raises an exception**. If nothing catches it, the program stops and prints a traceback. With `try` / `except` you can catch it and carry on.

```python
def safe_divide(a, b):
    try:
        result = a / b
    except ZeroDivisionError:
        print("can't divide by zero")
        return None
    else:
        return result            # runs only if no exception happened
    finally:
        print("done dividing")   # runs no matter what

print(safe_divide(10, 4))
print(safe_divide(1, 0))

for raw in ["12", "x7", "3.5"]:
    try:
        print(int(raw) * 2)
    except ValueError as e:
        print("not a whole number:", e)
```

You can raise your own exceptions to refuse bad input:

```python
def set_age(age):
    if age < 0:
        raise ValueError(f"age can't be negative: {age}")
    return age

try:
    set_age(-3)
except ValueError as e:
    print("refused:", e)
```

- Catch the **specific** exception you expect. A bare `except:` hides real bugs too, even typos.
- Common ones: `ValueError` (bad value), `TypeError` (wrong type), `KeyError`, `IndexError`, `ZeroDivisionError`, `FileNotFoundError`.

Things to try:

1. Remove the `try` and run `safe_divide(1, 0)`. Read the traceback from the bottom up.
2. Catch two kinds at once: `except (ValueError, TypeError):`.
3. Make your own exception class: `class TooCold(Exception): pass`.

## Exercise

Each input line is a calculation like `12 / 4` (two numbers and one of `+ - * /`, separated by spaces). The first line says how many follow. For each one print the result, or one of these messages instead of crashing:

- `bad number` if a number isn't a valid number,
- `division by zero` for division by zero,
- `bad operator` for anything else.

Print results as numbers with at most 2 decimals, without trailing zeros (so `3`, `2.5`, `0.33`).

```input
4
12 / 4
7 / 0
x + 1
2 % 3
```

```python starter
n = int(input())
for _ in range(n):
    a, op, b = input().split()
```

```python solution
import operator

OPS = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}

n = int(input())
for _ in range(n):
    a, op, b = input().split()
    try:
        x, y = float(a), float(b)
        if op not in OPS:
            raise KeyError(op)
        r = OPS[op](x, y)
    except ValueError:
        print("bad number")
    except ZeroDivisionError:
        print("division by zero")
    except KeyError:
        print("bad operator")
    else:
        print(f"{r:.2f}".rstrip("0").rstrip("."))
```

```tests
{"name": "example", "stdin": "4\n12 / 4\n7 / 0\nx + 1\n2 % 3\n", "expected": "3\ndivision by zero\nbad number\nbad operator"}
{"name": "decimals", "stdin": "2\n1 / 3\n2.5 * 2\n", "expected": "0.33\n5"}
{"name": "negative", "stdin": "1\n1 - 3.5\n", "expected": "-2.5", "hidden": true}
```
