---
title: Pointer arithmetic and 2D arrays
summary: Walking memory with p + i, and grids stored row by row.
---
Adding a number to a pointer moves it by that many **elements**, not bytes. If `p` points at an `int`, `p + 1` points at the next `int`, 4 bytes further on. That is all `a[i]` really is: `*(a + i)`.

```c
#include <stdio.h>

int main(void) {
    int a[5] = {10, 20, 30, 40, 50};
    int *p = a;                 /* same as &a[0] */

    printf("%d %d\n", *(p + 2), p[2]);     /* both 30 */
    p += 3;
    printf("%d\n", *p);                    /* 40 */
    printf("p is %ld elements past a\n", (long)(p - a));

    for (int *q = a; q < a + 5; q++) {     /* walk with a pointer */
        printf("%d ", *q);
    }
    printf("\n");
    return 0;
}
```

A **2D array** such as `int grid[3][4]` is 3 rows of 4 ints, stored one row after another. `grid[r][c]` is the element `r * 4 + c` places from the start.

```c
#include <stdio.h>

int main(void) {
    int grid[3][4] = {
        {1, 2, 3, 4},
        {5, 6, 7, 8},
        {9, 10, 11, 12},
    };
    for (int r = 0; r < 3; r++) {
        for (int c = 0; c < 4; c++) {
            printf("%3d", grid[r][c]);
        }
        printf("\n");
    }
    int *flat = &grid[0][0];
    printf("element 6 of the flat memory: %d\n", flat[6]);   /* row 1, column 2 */
    return 0;
}
```

To pass a 2D array to a function, give the column count in the parameter: `void show(int rows, int cols, int g[rows][cols])`.

Things to try:

1. Print the grid's column sums.
2. Print `(void *)&a[0]` and `(void *)&a[1]`. How far apart are the addresses?
3. Print the grid transposed (columns as rows).

## Exercise

The input is `r c` and then an `r × c` grid of whole numbers (at most 20 × 20). Print the grid rotated 90° clockwise: it has `c` rows of `r` numbers, separated by single spaces.

```input
2 3
1 2 3
4 5 6
```

```c starter
#include <stdio.h>

int main(void) {
    int r, c;
    int g[20][20];
    scanf("%d %d", &r, &c);
    for (int i = 0; i < r; i++) {
        for (int j = 0; j < c; j++) {
            scanf("%d", &g[i][j]);
        }
    }
    /* print g rotated 90 degrees clockwise */
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    int r, c;
    int g[20][20];
    scanf("%d %d", &r, &c);
    for (int i = 0; i < r; i++) {
        for (int j = 0; j < c; j++) {
            scanf("%d", &g[i][j]);
        }
    }
    for (int j = 0; j < c; j++) {
        for (int i = r - 1; i >= 0; i--) {
            printf("%d%s", g[i][j], i > 0 ? " " : "\n");
        }
    }
    return 0;
}
```

```tests
{"name": "2 x 3", "stdin": "2 3\n1 2 3\n4 5 6\n", "expected": "4 1\n5 2\n6 3"}
{"name": "1 x 1", "stdin": "1 1\n9\n", "expected": "9"}
{"name": "3 x 2", "stdin": "3 2\n1 2\n3 4\n5 6\n", "expected": "5 3 1\n6 4 2", "hidden": true}
```
