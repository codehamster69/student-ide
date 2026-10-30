---
title: Loops
summary: for over a range or a sequence, and while.
---
A `for` loop runs once for each item in a sequence. `range(n)` gives `0, 1, ..., n-1`, and `range(a, b, step)` counts from `a` up to (but not including) `b`.

```python
for i in range(1, 6):
    print(i, "x 7 =", i * 7)

for letter in "loop":
    print(letter.upper())
```

A `while` loop repeats as long as its condition holds:

```python
n = 27
steps = 0
while n != 1:
    n = n // 2 if n % 2 == 0 else 3 * n + 1
    steps += 1
print(steps, "steps")
```

Things to try:

1. Print the 7 times table backwards using `range(10, 0, -1)`.
2. Use `break` to stop the first loop as soon as the product is more than 20.
3. Change `n = 27` to other numbers. Does the `while` loop always end?

## Exercise

Read `n` and print the first `n` lines of this triangle (line `i` has `i` stars):

```
*
**
***
```

```input
3
```

```python starter
n = int(input())
```

```python solution
n = int(input())
for i in range(1, n + 1):
    print("*" * i)
```

```tests
{"name": "3", "stdin": "3\n", "expected": "*\n**\n***"}
{"name": "1", "stdin": "1\n", "expected": "*"}
{"name": "5", "stdin": "5\n", "expected": "*\n**\n***\n****\n*****"}
```
