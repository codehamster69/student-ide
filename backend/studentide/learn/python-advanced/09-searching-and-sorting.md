---
title: Searching and sorting algorithms
summary: How sorting works inside, binary search by hand and with bisect, and what "fast" means in big-O terms.
---
`sorted()` and `list.sort()` are fast and you should use them. But knowing how sorting works helps you reason about speed. **Merge sort** splits the list in half, sorts each half (recursively), and merges the two sorted halves:

```python
def merge_sort(a):
    if len(a) <= 1:
        return a
    mid = len(a) // 2
    left, right = merge_sort(a[:mid]), merge_sort(a[mid:])
    out, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            out.append(left[i]); i += 1
        else:
            out.append(right[j]); j += 1
    return out + left[i:] + right[j:]

print(merge_sort([5, 2, 9, 1, 5, 6]))
```

**Big-O** describes how the work grows with the input size `n`:

- `O(1)`: the same work for any `n` (a dict lookup).
- `O(log n)`: halves the problem each step (binary search; a million items take about 20 steps).
- `O(n)`: looks at everything once (`max`, `x in list`).
- `O(n log n)`: good sorting (merge sort, `sorted`).
- `O(n²)`: a loop inside a loop over the data (simple sorts, comparing every pair). Fine for 1 000 items, painful for 1 000 000.

**Binary search** finds a value in a *sorted* list by looking at the middle and throwing away the half it can't be in. The `bisect` module does it for you: `bisect_left(a, x)` is the first position where `x` could go without breaking the order, and `insort` inserts while keeping the list sorted.

```python
from bisect import bisect_left, bisect_right, insort

def binary_search(a, x):
    lo, hi = 0, len(a) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if a[mid] == x:
            return mid
        if a[mid] < x:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

a = [1, 3, 3, 3, 7, 9]
print(binary_search(a, 7), binary_search(a, 4))
print(bisect_left(a, 3), bisect_right(a, 3))    # 3 occupies positions 1 to 3
insort(a, 5)
print(a)
```

Things to try:

1. Count the comparisons `merge_sort` makes for 8, 16 and 32 items.
2. Use `bisect_right(a, x) - bisect_left(a, x)` to count copies of `x`.
3. Time `x in big_list` against `x in big_set` for a million numbers with the `time` module.

## Exercise

A teacher has the sorted list of cut-off marks for grades, and each grade's letter. Read the cut-offs, the letters (one more than the cut-offs), and then marks, one per line. For each mark print its grade. A mark below the first cut-off gets the first letter; a mark equal to a cut-off gets the higher grade. Use `bisect`.

```input
40 60 75 90
F D C B A
39
40
89
100
```

```python starter
import sys

cutoffs = list(map(int, input().split()))
letters = input().split()
for line in sys.stdin:
    print(letters[0])
```

```python solution
import sys
from bisect import bisect_right

cutoffs = list(map(int, input().split()))
letters = input().split()
for line in sys.stdin:
    if line.strip():
        print(letters[bisect_right(cutoffs, int(line))])
```

```tests
{"name": "example", "stdin": "40 60 75 90\nF D C B A\n39\n40\n89\n100\n", "expected": "F\nD\nB\nA"}
{"name": "one cut-off", "stdin": "50\nfail pass\n49\n50\n", "expected": "fail\npass"}
{"name": "zero", "stdin": "40 60 75 90\nF D C B A\n0\n75\n", "expected": "F\nB", "hidden": true}
```
