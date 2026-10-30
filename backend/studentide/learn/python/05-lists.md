---
title: Lists
summary: Store many values, loop over them, and use built-ins like sum and max.
---
A **list** holds values in order. Indexes start at 0, and negative indexes count from the end.

```python
marks = [72, 85, 64, 90, 58]
print(marks[0], marks[-1], len(marks))

marks.append(77)
marks[2] = 70
print(marks)
print("best", max(marks), "average", sum(marks) / len(marks))

passed = [m for m in marks if m >= 60]
print(passed, sorted(marks, reverse=True))
```

- `append` adds to the end; `sorted(...)` gives a new, sorted list.
- `marks[1:3]` is a *slice*: the items at index 1 and 2.
- `[m for m in marks if m >= 60]` is a *list comprehension*: a short way to build a new list from an old one.

Things to try:

1. Print `marks[::-1]`. What did the slice do?
2. Count marks below 60 with a loop, then with a comprehension and `len`.
3. What happens with `marks[10]`?

## Exercise

The input is one line of whole numbers separated by spaces. Print how many there are, then the second largest *different* value (there are always at least two different values).

```input
4 9 2 9 7
```

```python starter
nums = list(map(int, input().split()))
```

```python solution
nums = list(map(int, input().split()))
print(len(nums))
print(sorted(set(nums))[-2])
```

```tests
{"name": "with a repeat", "stdin": "4 9 2 9 7\n", "expected": "5\n7"}
{"name": "two values", "stdin": "1 2\n", "expected": "2\n1"}
{"name": "negatives", "stdin": "-5 -1 -3\n", "expected": "3\n-3"}
```
