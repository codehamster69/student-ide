---
title: Functions
summary: Give a piece of code a name, inputs and a result.
---
A **function** packages some code so you can use it again by name. It has a return type, a name, and a list of *parameters* (its inputs):

```c
#include <stdio.h>

int square(int x) {
    return x * x;
}

int bigger(int a, int b) {
    if (a > b) {
        return a;
    }
    return b;
}

int main(void) {
    printf("%d\n", square(9));
    printf("%d\n", bigger(3, 11));
    printf("%d\n", square(bigger(2, 5)));
    return 0;
}
```

- `return` hands a value back to whoever called the function, and leaves the function right away.
- A function that gives nothing back has the return type `void`.
- C reads the file from top to bottom, so a function must be defined (or at least declared) *before* it is called. Try moving `square` below `main` and look at the warning.

The parameters are **copies**. If `square` changed `x`, the caller's variable would not change. The pointers lesson shows how a function can change the caller's variables.

Things to try:

1. Write `int cube(int x)` and print `cube(4)`.
2. Write `void line(int n)` that prints `n` dashes and a newline.
3. What happens if you call `bigger(3)` with one argument?

## Exercise

Write the function `is_prime` so that it returns 1 if `n` is prime and 0 otherwise (numbers below 2 are not prime). `main` already reads a number and prints the answer.

```input
97
```

```c starter
#include <stdio.h>

int is_prime(int n) {
    /* return 1 if n is prime, 0 if not */
    return 0;
}

int main(void) {
    int n;
    scanf("%d", &n);
    if (is_prime(n)) {
        printf("%d is prime\n", n);
    } else {
        printf("%d is not prime\n", n);
    }
    return 0;
}
```

```c solution
#include <stdio.h>

int is_prime(int n) {
    if (n < 2) {
        return 0;
    }
    for (int d = 2; d * d <= n; d++) {
        if (n % d == 0) {
            return 0;
        }
    }
    return 1;
}

int main(void) {
    int n;
    scanf("%d", &n);
    if (is_prime(n)) {
        printf("%d is prime\n", n);
    } else {
        printf("%d is not prime\n", n);
    }
    return 0;
}
```

```tests
{"name": "97", "stdin": "97\n", "expected": "97 is prime"}
{"name": "91 = 7 x 13", "stdin": "91\n", "expected": "91 is not prime"}
{"name": "2", "stdin": "2\n", "expected": "2 is prime"}
{"name": "1", "stdin": "1\n", "expected": "1 is not prime"}
{"name": "a square of a prime", "stdin": "49\n", "expected": "49 is not prime", "hidden": true}
```
