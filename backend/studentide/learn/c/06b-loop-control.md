---
title: break, continue, do-while and nested loops
summary: Leave a loop early, skip a round, run at least once, and put loops inside loops.
---
Three tools change how a loop runs:

- `break` leaves the loop straight away.
- `continue` skips the rest of this round and starts the next one.
- `do { ... } while (condition);` runs the body first and tests afterwards, so it always runs at least once.

```c
#include <stdio.h>

int main(void) {
    /* add up positive numbers; skip negatives; stop at 0 */
    int x, sum = 0;
    while (1) {
        scanf("%d", &x);
        if (x == 0) break;
        if (x < 0) continue;
        sum += x;
    }
    printf("sum = %d\n", sum);

    int n = 0;
    do {
        printf("this runs once even though n is %d\n", n);
    } while (n > 0);
    return 0;
}
```

```input
4 -2 5 0
```

A loop inside another loop runs completely for every round of the outer one. Here the inner loop prints one row:

```c
#include <stdio.h>

int main(void) {
    for (int row = 1; row <= 4; row++) {
        for (int col = 1; col <= 4; col++) {
            printf("%3d", row * col);
        }
        printf("\n");
    }
    return 0;
}
```

`break` only leaves the innermost loop it is in.

Things to try:

1. In the first example, swap `break` and `continue`. What happens?
2. Make the table print only the cells where `col <= row` (a triangle).
3. Use a `do`-`while` loop to keep reading numbers until the user types one between 1 and 10.

## Exercise

Read `n` (at least 2) and print every prime number from 2 to `n` on one line, separated by spaces. A prime has no divisor between 2 and itself. Use an inner loop to look for a divisor and `break` as soon as you find one.

```input
20
```

```c starter
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    for (int i = 2; i <= n; i++) {
        /* is i prime? */
    }
    printf("\n");
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    int first = 1;
    for (int i = 2; i <= n; i++) {
        int prime = 1;
        for (int d = 2; d * d <= i; d++) {
            if (i % d == 0) {
                prime = 0;
                break;
            }
        }
        if (!prime) continue;
        printf(first ? "%d" : " %d", i);
        first = 0;
    }
    printf("\n");
    return 0;
}
```

```tests
{"name": "20", "stdin": "20\n", "expected": "2 3 5 7 11 13 17 19"}
{"name": "2", "stdin": "2\n", "expected": "2"}
{"name": "10", "stdin": "10\n", "expected": "2 3 5 7"}
{"name": "50", "stdin": "50\n", "expected": "2 3 5 7 11 13 17 19 23 29 31 37 41 43 47", "hidden": true}
```
