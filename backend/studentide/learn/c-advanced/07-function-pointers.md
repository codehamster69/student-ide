---
title: Function pointers and qsort
summary: Pass a function to another function, and sort anything with qsort.
---
A function also lives at an address, so you can store it in a variable and call it later. That lets one function take *behaviour* as a parameter.

```c
#include <stdio.h>

int add(int a, int b) { return a + b; }
int mul(int a, int b) { return a * b; }

/* op is a pointer to a function taking two ints and returning an int */
int fold(const int *a, int n, int start, int (*op)(int, int)) {
    int acc = start;
    for (int i = 0; i < n; i++) {
        acc = op(acc, a[i]);
    }
    return acc;
}

int main(void) {
    int a[] = {1, 2, 3, 4, 5};
    printf("sum %d\n", fold(a, 5, 0, add));
    printf("product %d\n", fold(a, 5, 1, mul));
    return 0;
}
```

The standard library's **`qsort`** (in `<stdlib.h>`) sorts any array. You tell it how to compare two elements with a function that gets two `const void *` pointers and returns a negative number, zero or a positive number:

```c
#include <stdio.h>
#include <stdlib.h>

int ascending(const void *x, const void *y) {
    int a = *(const int *)x, b = *(const int *)y;
    return (a > b) - (a < b);     /* -1, 0 or 1, and never overflows */
}

int main(void) {
    int a[] = {42, 7, 19, 3, 25};
    qsort(a, 5, sizeof(int), ascending);
    for (int i = 0; i < 5; i++) printf("%d ", a[i]);
    printf("\n");
    return 0;
}
```

`void *` means "a pointer to something, type unknown". The comparison function casts it back to the real type.

Things to try:

1. Write `descending` and sort the other way.
2. Add `int max2(int a, int b)` and use `fold` to find the largest element.
3. Sort an array of strings: the elements are `char *`, so the comparator gets `char **` and calls `strcmp`.

## Exercise

Read `n` (at most 1000) and then `n` lines, each a name (one word, at most 30 letters) and a score. Sort with `qsort`: higher score first, and equal scores by name in alphabetical order. Print one `name score` per line.

```input
4
ravi 80
asha 95
neel 80
zoya 70
```

```c starter
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char name[32];
    int score;
} Entry;

int by_rank(const void *x, const void *y) {
    /* higher score first; equal scores by name */
    return 0;
}

int main(void) {
    int n;
    static Entry e[1000];
    scanf("%d", &n);
    for (int i = 0; i < n; i++) {
        scanf("%31s %d", e[i].name, &e[i].score);
    }
    qsort(e, n, sizeof(Entry), by_rank);
    for (int i = 0; i < n; i++) {
        printf("%s %d\n", e[i].name, e[i].score);
    }
    return 0;
}
```

```c solution
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char name[32];
    int score;
} Entry;

int by_rank(const void *x, const void *y) {
    const Entry *a = x, *b = y;
    if (a->score != b->score) {
        return b->score - a->score;
    }
    return strcmp(a->name, b->name);
}

int main(void) {
    int n;
    static Entry e[1000];
    scanf("%d", &n);
    for (int i = 0; i < n; i++) {
        scanf("%31s %d", e[i].name, &e[i].score);
    }
    qsort(e, n, sizeof(Entry), by_rank);
    for (int i = 0; i < n; i++) {
        printf("%s %d\n", e[i].name, e[i].score);
    }
    return 0;
}
```

```tests
{"name": "with a tie", "stdin": "4\nravi 80\nasha 95\nneel 80\nzoya 70\n", "expected": "asha 95\nneel 80\nravi 80\nzoya 70"}
{"name": "already sorted", "stdin": "2\nb 2\na 1\n", "expected": "b 2\na 1"}
{"name": "all tied", "stdin": "3\nc 5\na 5\nb 5\n", "expected": "a 5\nb 5\nc 5", "hidden": true}
```
