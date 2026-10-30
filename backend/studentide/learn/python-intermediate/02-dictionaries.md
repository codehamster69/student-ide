---
title: Dictionaries
summary: Look values up by key, count things, and group them.
---
A **dictionary** maps *keys* to *values*. Looking a key up is fast no matter how big the dictionary is.

```python
marks = {"asha": 91, "ravi": 78}
marks["neel"] = 85                    # add or replace
print(marks["asha"], len(marks))
print(marks.get("zoya", "absent"))   # a default instead of an error
for name, m in marks.items():
    print(name, m)

# counting: the classic dictionary job
text = "the cat and the hat and the bat"
counts = {}
for w in text.split():
    counts[w] = counts.get(w, 0) + 1
print(counts)
```

- `d[key]` raises `KeyError` if the key is missing; `d.get(key, default)` doesn't.
- `d.keys()`, `d.values()` and `d.items()` let you loop over a dictionary.
- Keys must be immutable (strings, numbers, tuples). Lists can't be keys.
- `collections.Counter` and `collections.defaultdict` make counting and grouping even shorter: `Counter(text.split()).most_common(2)`.

Things to try:

1. Delete a key with `del marks["ravi"]`, then look it up with `[]` and with `get`.
2. Group words by their first letter into a dictionary of lists.
3. Use `Counter` to find the most common letter in a sentence.

## Exercise

Read a line of words and print each distinct word with its count, one per line as `word count`, most frequent first; words with the same count in alphabetical order. Treat upper and lower case as the same word (print it in lower case).

```input
The cat and the hat and THE bat
```

```python starter
words = input().lower().split()
```

```python solution
from collections import Counter

counts = Counter(input().lower().split())
for word, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
    print(word, n)
```

```tests
{"name": "cat and hat", "stdin": "The cat and the hat and THE bat\n", "expected": "the 3\nand 2\nbat 1\ncat 1\nhat 1"}
{"name": "one word", "stdin": "hi\n", "expected": "hi 1"}
{"name": "ties", "stdin": "b a b a c\n", "expected": "a 2\nb 2\nc 1", "hidden": true}
```
