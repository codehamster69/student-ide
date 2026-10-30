---
title: Scope and lifetime
summary: Where a variable can be used, how long it lives, local versus global, and static locals.
---
A variable's **scope** is the part of the program that can see it. A variable declared inside `{ }` exists only inside those braces. Each function call gets fresh copies of its local variables, and they disappear when the function returns.

```c
#include <stdio.h>

int total = 0;            /* global: every function can see it */

void add(int x) {
    int doubled = x * 2;  /* local: only add() can see it */
    total += doubled;
}

int main(void) {
    add(3);
    add(4);
    printf("total = %d\n", total);
    for (int i = 0; i < 2; i++) {
        int square = i * i;   /* lives only inside the loop body */
        printf("%d\n", square);
    }
    /* printf("%d", square);  would not compile: square is out of scope */
    return 0;
}
```

If an inner block declares a variable with the same name as an outer one, the inner one **shadows** it: inside the block the name means the inner variable. This compiles, but it is a common source of confusing bugs.

Globals are easy to use but hard to reason about, because any function can change them. Prefer passing values as parameters and returning results.

A `static` local variable is in between: only its function can see it, but it keeps its value between calls. It is set up once, before the first call.

```c
#include <stdio.h>

int calls(void) {
    static int count = 0;   /* not reset on each call */
    count++;
    return count;
}

int main(void) {
    for (int i = 0; i < 3; i++) printf("called %d times\n", calls());
    return 0;
}
```

Things to try:

1. Remove `static` from `count`. What does the program print now?
2. Inside `main`, declare `int total = 100;` before calling `add`. What does `printf` show, and why?
3. Try to print `doubled` from `main`. Read the compiler's message.

## Exercise

Write `int next_ticket(void)`, which returns 101 the first time it is called, then 102, 103 and so on, without using a global variable. The `main` function is given: it reads `n` and prints `n` tickets.

```input
3
```

```c starter
#include <stdio.h>

int next_ticket(void) {
    int ticket = 100;
    ticket++;
    return ticket;
}

int main(void) {
    int n;
    scanf("%d", &n);
    for (int i = 0; i < n; i++) printf("%d\n", next_ticket());
    return 0;
}
```

```c solution
#include <stdio.h>

int next_ticket(void) {
    static int ticket = 100;
    ticket++;
    return ticket;
}

int main(void) {
    int n;
    scanf("%d", &n);
    for (int i = 0; i < n; i++) printf("%d\n", next_ticket());
    return 0;
}
```

```tests
{"name": "3", "stdin": "3\n", "expected": "101\n102\n103"}
{"name": "1", "stdin": "1\n", "expected": "101"}
{"name": "5", "stdin": "5\n", "expected": "101\n102\n103\n104\n105", "hidden": true}
```
