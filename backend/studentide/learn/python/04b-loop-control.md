---
title: break, continue and nested loops
summary: Leave a loop early, skip a round, loop forever on purpose, and put loops inside loops.
---
- `break` leaves the loop at once.
- `continue` skips the rest of this round and moves on to the next.
- `while True:` loops forever, so it needs a `break` somewhere. It is the usual way to repeat "until something happens".

```python
total = 0
while True:
    x = int(input())
    if x == 0:
        break          # stop at 0
    if x < 0:
        continue       # skip negatives
    total += x
print("total", total)
```

```input
4
-2
5
0
```

A `for` or `while` loop can have an `else` block. It runs only if the loop finished **without** a `break`, which is handy for searches:

```python
n = 91
for d in range(2, n):
    if n % d == 0:
        print(n, "=", d, "x", n // d)
        break
else:
    print(n, "is prime")
```

A loop inside a loop runs fully for each round of the outer one:

```python
for row in range(1, 5):
    for col in range(1, 5):
        print(f"{row * col:3}", end="")
    print()
```

`print(..., end="")` stops `print` from starting a new line. `break` only leaves the innermost loop.

Things to try:

1. Change `n = 91` to `97`. Which branch runs now?
2. Make the table print only the cells where `col <= row`.
3. In the first example, what happens if you swap `break` and `continue`?

## Exercise

Read numbers, one per line, until a line says `done`. Ignore any number that is negative. Print how many numbers were counted and their total, like `3 numbers, total 12`.

```input
5
-1
3
4
done
```

```python starter
count = 0
total = 0
x = input()
print(f"{count} numbers, total {total}")
```

```python solution
count = 0
total = 0
while True:
    line = input()
    if line == "done":
        break
    x = int(line)
    if x < 0:
        continue
    count += 1
    total += x
print(f"{count} numbers, total {total}")
```

```tests
{"name": "example", "stdin": "5\n-1\n3\n4\ndone\n", "expected": "3 numbers, total 12"}
{"name": "none", "stdin": "done\n", "expected": "0 numbers, total 0"}
{"name": "all negative", "stdin": "-3\n-4\ndone\n", "expected": "0 numbers, total 0"}
{"name": "zeros count", "stdin": "0\n0\n10\ndone\n", "expected": "3 numbers, total 10", "hidden": true}
```
