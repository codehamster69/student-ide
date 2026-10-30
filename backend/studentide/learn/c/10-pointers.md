---
title: Pointers
summary: Addresses, & and *, and letting a function change your variables.
---
Every variable lives somewhere in memory, at an **address**. A **pointer** is a variable that holds an address.

- `&x` is "the address of `x`".
- `int *p` declares `p` as a pointer to an `int`.
- `*p` is "the value at the address in `p`". You can read it and also assign to it.

```c
#include <stdio.h>

int main(void) {
    int x = 10;
    int *p = &x;          /* p points at x */

    printf("x = %d, *p = %d\n", x, *p);
    *p = 25;              /* changes x through the pointer */
    printf("x is now %d\n", x);
    printf("x lives at %p\n", (void *)p);
    return 0;
}
```

This is why `scanf` needs `&`: it gets the *address* of your variable, so it can write into it. Your own functions can do the same:

```c
#include <stdio.h>

void add_ten(int *n) {
    *n = *n + 10;
}

int main(void) {
    int score = 5;
    add_ten(&score);
    printf("%d\n", score);   /* 15 */
    return 0;
}
```

An array's name works as a pointer to its first element, and `p + 1` points at the next element. So `a[i]` and `*(a + i)` mean the same thing.

Things to try:

1. Change `add_ten` to take a plain `int n`. Why does `score` stay 5?
2. Make a second pointer `int *q = p;` and change `x` through `q`.
3. Walk an array with a pointer: `for (int *q = a; q < a + 5; q++) printf("%d ", *q);`

## Exercise

Write `swap` so that it exchanges the two values its arguments point to. `main` reads two numbers, swaps them and prints them.

```input
3 8
```

```c starter
#include <stdio.h>

void swap(int *a, int *b) {
    /* exchange *a and *b */
}

int main(void) {
    int x, y;
    scanf("%d %d", &x, &y);
    swap(&x, &y);
    printf("%d %d\n", x, y);
    return 0;
}
```

```c solution
#include <stdio.h>

void swap(int *a, int *b) {
    int t = *a;
    *a = *b;
    *b = t;
}

int main(void) {
    int x, y;
    scanf("%d %d", &x, &y);
    swap(&x, &y);
    printf("%d %d\n", x, y);
    return 0;
}
```

```tests
{"name": "3 8", "stdin": "3 8\n", "expected": "8 3"}
{"name": "equal", "stdin": "4 4\n", "expected": "4 4"}
{"name": "negatives", "stdin": "-1 6\n", "expected": "6 -1", "hidden": true}
```
