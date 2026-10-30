---
title: Recursion
summary: A function that calls itself on a smaller problem.
---
A function may call **itself**. That is useful when a problem contains a smaller copy of the same problem. Every recursive function needs two parts:

1. a **base case** that answers directly, without calling itself, and
2. a **recursive case** that calls itself on a *smaller* input, moving towards the base case.

```c
#include <stdio.h>

long factorial(int n) {
    if (n <= 1) {
        return 1;                    /* base case */
    }
    return n * factorial(n - 1);     /* smaller problem */
}

int main(void) {
    for (int i = 0; i <= 10; i++) {
        printf("%d! = %ld\n", i, factorial(i));
    }
    return 0;
}
```

Think of `factorial(4)`: it waits for `factorial(3)`, which waits for `factorial(2)`, then `factorial(1)` returns 1, and the answers multiply back up: 2, 6, 24.

Things to try:

1. Remove the base case. The program never stops calling itself and crashes with a *stack overflow*.
2. Add `printf("enter %d\n", n);` at the top of `factorial` to watch the calls happen.
3. Write `int power(int b, int e)` that computes `b` to the power `e` recursively.

## Exercise

Write `fib` recursively: `fib(0) = 0`, `fib(1) = 1`, and every later number is the sum of the two before it. `main` reads `n` (at most 30) and prints `fib(n)`.

```input
10
```

```c starter
#include <stdio.h>

int fib(int n) {
    /* base cases, then the recursive case */
    return 0;
}

int main(void) {
    int n;
    scanf("%d", &n);
    printf("%d\n", fib(n));
    return 0;
}
```

```c solution
#include <stdio.h>

int fib(int n) {
    if (n < 2) {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}

int main(void) {
    int n;
    scanf("%d", &n);
    printf("%d\n", fib(n));
    return 0;
}
```

```tests
{"name": "fib(10)", "stdin": "10\n", "expected": "55"}
{"name": "fib(1)", "stdin": "1\n", "expected": "1"}
{"name": "fib(2)", "stdin": "2\n", "expected": "1"}
{"name": "fib(25)", "stdin": "25\n", "expected": "75025", "hidden": true}
```
