---
title: The collections and heapq modules
summary: Counter, defaultdict, deque, namedtuple, and heapq for always getting the smallest item fast.
---
The `collections` module has containers that save you from writing the same few lines again and again.

**Counter** counts things. Give it any sequence; `most_common(k)` gives the top `k`.

```python
from collections import Counter

votes = Counter("ABACABBA")
print(votes)                 # Counter({'A': 4, 'B': 3, 'C': 1})
print(votes["B"], votes["Z"])   # a missing key counts as 0
print(votes.most_common(2))
```

**defaultdict** builds a default value the first time a key is used, so grouping needs no `if key not in d` check.

```python
from collections import defaultdict

by_letter = defaultdict(list)
for word in ["apple", "avocado", "banana", "blueberry", "cherry"]:
    by_letter[word[0]].append(word)
print(dict(by_letter))
```

**deque** ("deck") is a list that is fast at both ends: `append`, `appendleft`, `pop`, `popleft`. Use it for queues; `list.pop(0)` is slow because it shifts everything. With `maxlen` it keeps only the last few items.

```python
from collections import deque, namedtuple

q = deque([1, 2, 3])
q.appendleft(0)
q.append(4)
print(q.popleft(), q)
recent = deque(maxlen=3)
for x in range(6):
    recent.append(x)
print(list(recent))          # [3, 4, 5]

Point = namedtuple("Point", ["x", "y"])   # a tuple with named fields
p = Point(3, 4)
print(p.x, p[1], p)
```

**heapq** keeps a list arranged so the smallest item is always at index 0. `heappush` and `heappop` are fast even for huge lists, which makes it a priority queue. `nsmallest` and `nlargest` pick the top few without sorting everything.

```python
import heapq

tasks = []
heapq.heappush(tasks, (3, "write report"))
heapq.heappush(tasks, (1, "fix bug"))
heapq.heappush(tasks, (2, "reply to email"))
while tasks:
    priority, name = heapq.heappop(tasks)
    print(priority, name)
print(heapq.nlargest(2, [5, 1, 9, 3]))
```

Things to try:

1. Add two Counters together with `+`.
2. Use a `deque` to rotate a list: look up `q.rotate(1)`.
3. Push `(2, "a")` and `(2, "b")` onto a heap. Which comes out first, and why?

## Exercise

Read a line of words. Print the three most common words with their counts, like `the 3`, most common first. When two words have the same count, put the one that comes first alphabetically first. If there are fewer than three different words, print all of them.

```input
the cat and the dog and the bird
```

```python starter
words = input().split()
for w in words[:3]:
    print(w, 1)
```

```python solution
from collections import Counter

words = input().split()
counts = Counter(words)
top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
for word, n in top:
    print(word, n)
```

```tests
{"name": "example", "stdin": "the cat and the dog and the bird\n", "expected": "the 3\nand 2\nbird 1"}
{"name": "two words", "stdin": "b a b\n", "expected": "b 2\na 1"}
{"name": "all ties", "stdin": "d c b a\n", "expected": "a 1\nb 1\nc 1", "hidden": true}
```
