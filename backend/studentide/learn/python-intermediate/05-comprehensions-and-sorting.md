---
title: Comprehensions, lambda and sorting
summary: Build collections in one line and sort by any rule you like.
---
A **comprehension** builds a list, set or dictionary from another collection in one expression:

```python
nums = [5, 3, 8, 1, 9, 2]
squares = [n * n for n in nums]
evens = [n for n in nums if n % 2 == 0]
lengths = {w: len(w) for w in ["loop", "if", "function"]}
unique_mods = {n % 3 for n in nums}
pairs = [(r, c) for r in range(2) for c in range(3)]
print(squares, evens, lengths, unique_mods, pairs, sep="\n")
```

`sorted` (and `list.sort`) take a `key` function: Python sorts by whatever the key returns. A **`lambda`** is a small unnamed function, handy for keys:

```python
students = [("asha", 91), ("ravi", 78), ("neel", 91), ("zoya", 85)]
print(sorted(students, key=lambda s: s[1]))               # by marks
print(sorted(students, key=lambda s: (-s[1], s[0])))      # marks high-low, then name
print(max(students, key=lambda s: s[1]))
words = ["banana", "Apple", "cherry"]
print(sorted(words), sorted(words, key=str.lower))
```

- Sorting by a tuple sorts by the first item, then breaks ties with the next.
- `-s[1]` flips a number's order; for strings use `reverse=True` or sort twice (Python's sort is *stable*: equal items keep their order).
- `enumerate`, `zip`, `any`, `all`, `sum` and `min`/`max` combine well with comprehensions.

Things to try:

1. Make a list of the words longer than 4 letters, in upper case, in one line.
2. Sort the students by name length, then by name.
3. Use `zip(names, marks)` to pair two lists, then make a dictionary with `dict(...)`.

## Exercise

The first line is `n`; then `n` lines of `name city age`. Print the people sorted by city (A to Z), then by age (oldest first), then by name, one `name city age` per line.

```input
4
asha surat 21
ravi pune 19
neel surat 23
zoya pune 19
```

```python starter
n = int(input())
people = [input().split() for _ in range(n)]
```

```python solution
n = int(input())
people = [input().split() for _ in range(n)]
for name, city, age in sorted(people, key=lambda p: (p[1], -int(p[2]), p[0])):
    print(name, city, age)
```

```tests
{"name": "example", "stdin": "4\nasha surat 21\nravi pune 19\nneel surat 23\nzoya pune 19\n", "expected": "ravi pune 19\nzoya pune 19\nneel surat 23\nasha surat 21"}
{"name": "ages as numbers", "stdin": "2\na x 9\nb x 10\n", "expected": "b x 10\na x 9", "hidden": true}
```
