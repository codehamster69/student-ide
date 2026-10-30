---
title: Printing and values
summary: print, strings, numbers and f-strings.
---
Python runs your file from the first line to the last. `print` shows values, separated by spaces, and ends with a newline.

```python
print("Hello!")
print("2 + 3 =", 2 + 3)
print(7 / 2, 7 // 2, 7 % 2, 2 ** 10)

name = "Ada"
year = 1843
print(f"{name} wrote the first program in {year}.")
```

- Text goes in quotes: `"..."` or `'...'`.
- `/` always gives a decimal answer; `//` divides and drops the remainder; `%` is the remainder; `**` is a power.
- An **f-string** (`f"..."`) puts the value of anything inside `{ }` into the text.

Things to try:

1. Print your own name and age with an f-string.
2. What does `print("ab" * 3)` do? And `print("ab" + "cd")`?
3. Add `sep="-"` to a `print` with several values: `print(1, 2, 3, sep="-")`.

## Exercise

Make the program print exactly:

```
Python says hi
1024
```

The second line must be computed as a power of 2, not typed in.

```python starter
print("Hello!")
```

```python solution
print("Python says hi")
print(2 ** 10)
```

```tests
{"name": "two lines", "stdin": "", "expected": "Python says hi\n1024"}
```
