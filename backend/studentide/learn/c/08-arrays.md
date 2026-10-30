---
title: Arrays
summary: Keep many values of one type under one name.
---
An **array** is a row of boxes of the same type, numbered from **0**. `int marks[5];` makes five `int`s: `marks[0]` up to `marks[4]`.

```c
#include <stdio.h>

int main(void) {
    int marks[5] = {72, 85, 64, 90, 58};
    int total = 0;

    for (int i = 0; i < 5; i++) {
        total += marks[i];
    }
    printf("total %d, average %.1f\n", total, total / 5.0);

    marks[2] = 70;           /* change one element */
    printf("third mark is now %d\n", marks[2]);
    return 0;
}
```

Loops and arrays go together: the loop variable walks along the indexes `0, 1, ..., n-1`.

C does **not** check that an index is inside the array. `marks[5]` or `marks[-1]` reads memory that belongs to something else, which can print rubbish or crash the program. Try it and see.

Things to try:

1. Find the largest mark with a loop (start with `int best = marks[0];`).
2. Print the marks in reverse order.
3. Count how many marks are 60 or more.

## Exercise

The input is a count `n` (at most 100) followed by `n` whole numbers. Print the numbers in reverse order, separated by single spaces, on one line.

```input
5
3 1 4 1 5
```

```c starter
#include <stdio.h>

int main(void) {
    int n;
    int a[100];
    scanf("%d", &n);
    for (int i = 0; i < n; i++) {
        scanf("%d", &a[i]);
    }
    /* print a in reverse order */
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    int n;
    int a[100];
    scanf("%d", &n);
    for (int i = 0; i < n; i++) {
        scanf("%d", &a[i]);
    }
    for (int i = n - 1; i >= 0; i--) {
        printf("%d", a[i]);
        if (i > 0) {
            printf(" ");
        }
    }
    printf("\n");
    return 0;
}
```

```tests
{"name": "five numbers", "stdin": "5\n3 1 4 1 5\n", "expected": "5 1 4 1 3"}
{"name": "one number", "stdin": "1\n42\n", "expected": "42"}
{"name": "negatives", "stdin": "4\n-1 0 -2 7\n", "expected": "7 -2 0 -1", "hidden": true}
```
