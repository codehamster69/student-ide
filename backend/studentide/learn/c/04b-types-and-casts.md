---
title: Types, division and casts
summary: Integer division, converting between types, sizeof, and what happens when a number gets too big.
---
C does arithmetic in the type of its operands. Two `int`s give an `int`, so `7 / 2` is `3`: the fraction is thrown away, not rounded. If either side is a `double`, the result is a `double`.

```c
#include <stdio.h>

int main(void) {
    int a = 7, b = 2;
    printf("%d\n", a / b);                 /* 3 */
    printf("%d\n", a % b);                 /* 1 */
    printf("%f\n", a / b);                 /* wrong! %f needs a double */
    printf("%.2f\n", (double)a / b);       /* 3.50: the cast makes a a double first */
    printf("%.2f\n", (double)(a / b));     /* 3.00: too late, the division already happened */
    return 0;
}
```

A **cast** `(type)value` converts a value to another type. Going from `double` to `int` cuts off the fraction: `(int)3.99` is `3`, and `(int)-3.99` is `-3`.

Every type has a size in bytes, which `sizeof` tells you. On the lab computers an `int` is 4 bytes, so it holds values from about -2.1 billion to 2.1 billion. Going past the end is called **overflow**. For `int` it is undefined behaviour (anything may happen), so use `long long` (8 bytes, printed with `%lld`) for big numbers.

```c
#include <stdio.h>
#include <limits.h>

int main(void) {
    printf("int: %zu bytes, max %d\n", sizeof(int), INT_MAX);
    printf("long long: %zu bytes, max %lld\n", sizeof(long long), LLONG_MAX);
    long long big = 100000LL * 100000LL;   /* the LL makes the multiplication 64-bit */
    printf("%lld\n", big);
    char c = 'A';
    printf("%c is stored as %d, and %c comes next\n", c, c, c + 1);
    return 0;
}
```

Characters are small integers, so `'A' + 1` is `'B'` and `'7' - '0'` is the number 7.

`<math.h>` has `sqrt`, `pow`, `fabs`, `floor`, `ceil` and `round`. They all take and return `double`.

Things to try:

1. Print `1 / 3` and `1.0 / 3`. Why are they different?
2. Print `2147483647 + 1` as an `int`, then do the same sum with `long long`.
3. Print `(int)'a'` and `(char)98`.

## Exercise

Read two integers `a` and `b` (with `b` not zero) and print, separated by spaces: the integer quotient, the remainder, and the exact quotient with two decimals.

```input
7 2
```

```c starter
#include <stdio.h>

int main(void) {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d\n", a / b);
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d %d %.2f\n", a / b, a % b, (double)a / b);
    return 0;
}
```

```tests
{"name": "7 2", "stdin": "7 2\n", "expected": "3 1 3.50"}
{"name": "10 4", "stdin": "10 4\n", "expected": "2 2 2.50"}
{"name": "9 3", "stdin": "9 3\n", "expected": "3 0 3.00"}
{"name": "1 3", "stdin": "1 3\n", "expected": "0 1 0.33", "hidden": true}
```
