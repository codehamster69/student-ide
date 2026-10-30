---
title: Tuples and sets
summary: Fixed records with tuples, and fast membership and set algebra with sets.
---
A **tuple** is like a list that can't change. It is good for small fixed records, and for returning several values from a function.

```python
point = (3, 4)
x, y = point                          # unpacking
print(x, y, point[0])

def min_max(nums):
    return min(nums), max(nums)       # really returns one tuple

lo, hi = min_max([7, 2, 9, 4])
print(lo, hi)
a, b = 1, 2
a, b = b, a                           # swap, no temporary
print(a, b)
```

A **set** holds unique values with no order. Checking `x in s` is fast, and sets support maths-style operations:

```python
python = {"asha", "ravi", "neel", "zoya"}
c_lang = {"ravi", "zoya", "meera"}
print(python & c_lang)      # in both
print(python | c_lang)      # in either
print(python - c_lang)      # only python
print(python ^ c_lang)      # in exactly one
print(set("mississippi"))   # unique letters
```

Things to try:

1. Remove duplicates from a list while keeping the first-seen order (a set plus a loop).
2. Try `point[0] = 5`. What error do you get?
3. Use a tuple `(row, col)` as a dictionary key for a grid.

## Exercise

The first input line lists the students who came on Monday, the second those who came on Tuesday (names separated by spaces). Print three lines: the names that came both days, the names that came only on Monday, and how many different students came in total. Print the names sorted alphabetically and separated by spaces (print `-` for an empty list).

```input
asha ravi neel zoya
ravi zoya meera
```

```python starter
monday = set(input().split())
tuesday = set(input().split())
```

```python solution
monday = set(input().split())
tuesday = set(input().split())
def show(names):
    print(" ".join(sorted(names)) if names else "-")
show(monday & tuesday)
show(monday - tuesday)
print(len(monday | tuesday))
```

```tests
{"name": "example", "stdin": "asha ravi neel zoya\nravi zoya meera\n", "expected": "ravi zoya\nasha neel\n5"}
{"name": "same people", "stdin": "a b\nb a\n", "expected": "a b\n-\n2"}
{"name": "nobody twice", "stdin": "a\nb\n", "expected": "-\na\n2", "hidden": true}
```
