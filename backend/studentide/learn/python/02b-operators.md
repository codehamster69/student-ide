---
title: Numbers, operators and True/False
summary: The arithmetic operators, // and %, rounding, converting between types, and booleans with and, or and not.
---
Python has two kinds of division. `/` always gives a decimal (`7 / 2` is `3.5`). `//` gives the whole-number part, rounded down (`7 // 2` is `3`), and `%` gives the remainder (`7 % 2` is `1`). `**` is "to the power of".

```python
print(7 / 2, 7 // 2, 7 % 2, 2 ** 10)
print(-7 // 2)            # -4: // always rounds down, not towards zero
print(round(2.675, 2))    # 2.67, not 2.68: decimals are stored approximately
print(0.1 + 0.2 == 0.3)   # False, for the same reason
print(abs(-5), max(3, 9, 4), min(3, 9, 4))
```

Python's integers have no size limit: `2 ** 200` just works. Converting between types:

- `int("42")` and `float("3.5")` turn text into numbers; `str(42)` goes back.
- `int(3.99)` cuts off the fraction (gives `3`); `round(3.5)` rounds (gives `4`).
- `type(x)` tells you what type `x` is.

Comparisons give `True` or `False`, the two values of type `bool`. Combine them with `and`, `or` and `not`. Python lets you chain comparisons: `0 <= x < 10` means `0 <= x and x < 10`.

```python
age = 16
print(age >= 13 and age <= 19)
print(13 <= age <= 19)          # the same, chained
print(not (age < 18))
print(True + True)              # 2: True counts as 1
print(bool(0), bool(""), bool("hi"), bool([]))
```

Zero, the empty string, empty lists and `None` count as false in an `if`; almost everything else counts as true.

Things to try:

1. Print `10 // 3`, `10 % 3`, `-10 // 3` and `-10 % 3`. Check that `(a // b) * b + a % b == a` every time.
2. Print `int("3.5")`. What goes wrong, and how would you fix it?
3. Print `2 ** 100` and `2.0 ** 100`. Why do they look different?

## Exercise

Read a number of seconds and print it as hours, minutes and seconds in the form `H:MM:SS`, where minutes and seconds always have two digits. Use `//` and `%`. (In an f-string, `{m:02}` pads a number to two digits.)

```input
3725
```

```python starter
total = int(input())
print(total)
```

```python solution
total = int(input())
h = total // 3600
m = total % 3600 // 60
s = total % 60
print(f"{h}:{m:02}:{s:02}")
```

```tests
{"name": "3725", "stdin": "3725\n", "expected": "1:02:05"}
{"name": "59", "stdin": "59\n", "expected": "0:00:59"}
{"name": "a day", "stdin": "86400\n", "expected": "24:00:00"}
{"name": "zero", "stdin": "0\n", "expected": "0:00:00", "hidden": true}
```
