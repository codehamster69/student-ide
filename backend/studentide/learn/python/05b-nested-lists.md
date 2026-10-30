---
title: Lists of lists
summary: Grids and tables as nested lists, reading a matrix, and the [[0] * n] * m trap.
---
A list can hold other lists, which is how Python stores a grid or a table. `grid[r][c]` is row `r`, column `c`.

```python
grid = [
    [1, 2, 3],
    [4, 5, 6],
]
print(grid[1][2])            # 6: row 1, column 2
print(len(grid), len(grid[0]))   # 2 rows, 3 columns
for row in grid:
    print(" ".join(str(x) for x in row))
print(sum(sum(row) for row in grid))
```

To read a matrix from input, read the size and then one list per line:

```python
r, c = map(int, input().split())
m = [list(map(int, input().split())) for _ in range(r)]
print(m)
```

```input
2 3
1 2 3
4 5 6
```

Building an empty grid has a famous trap. `[[0] * 3] * 2` makes **one** inner list and puts it in the outer list twice, so changing one row changes "both":

```python
bad = [[0] * 3] * 2
bad[0][0] = 9
print(bad)                       # [[9, 0, 0], [9, 0, 0]]

good = [[0] * 3 for _ in range(2)]   # a new inner list each time
good[0][0] = 9
print(good)                      # [[9, 0, 0], [0, 0, 0]]
```

Things to try:

1. Print the grid's diagonal, `grid[i][i]`, for a 3 by 3 grid.
2. Print each column's sum.
3. Check `bad[0] is bad[1]` and `good[0] is good[1]`.

## Exercise

Read `r` and `c`, then a matrix of `r` rows and `c` columns. Print its **transpose**: the matrix with rows and columns swapped, so it has `c` rows of `r` numbers each, separated by spaces.

```input
2 3
1 2 3
4 5 6
```

```python starter
r, c = map(int, input().split())
m = [list(map(int, input().split())) for _ in range(r)]
for row in m:
    print(" ".join(map(str, row)))
```

```python solution
r, c = map(int, input().split())
m = [list(map(int, input().split())) for _ in range(r)]
for j in range(c):
    print(" ".join(str(m[i][j]) for i in range(r)))
```

```tests
{"name": "2x3", "stdin": "2 3\n1 2 3\n4 5 6\n", "expected": "1 4\n2 5\n3 6"}
{"name": "1x2", "stdin": "1 2\n7 8\n", "expected": "7\n8"}
{"name": "3x1", "stdin": "3 1\n1\n2\n3\n", "expected": "1 2 3", "hidden": true}
```
