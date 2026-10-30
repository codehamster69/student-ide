---
title: Input and variables
summary: Read what the user types and turn it into numbers.
---
`input()` reads one line of text from the **Input** box. It always gives a *string*, so to do arithmetic you convert it with `int(...)` or `float(...)`.

```python
name = input()
age = int(input())
print(f"Hi {name}! Next year you will be {age + 1}.")
```

To read several numbers from one line, split it on spaces:

```python
a, b = map(int, input().split())
print(a * b)
```

Things to try:

1. Remove `int(...)` around the second `input()`. What error do you get, and why?
2. Change the Input box and run again.
3. Read a decimal price with `float` and print it with two decimals: `f"{price:.2f}"`.

## Exercise

The input is two whole numbers on one line. Print their sum, difference and product on three lines.

```input
12 5
```

```python starter
a, b = map(int, input().split())
# print a + b, a - b and a * b
```

```python solution
a, b = map(int, input().split())
print(a + b)
print(a - b)
print(a * b)
```

```tests
{"name": "12 5", "stdin": "12 5\n", "expected": "17\n7\n60"}
{"name": "negatives", "stdin": "-3 4\n", "expected": "1\n-7\n-12"}
```
