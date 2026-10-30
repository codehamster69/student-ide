---
title: Arithmetic and remainders
summary: The five arithmetic operators, and why % is so useful.
---
C has the usual `+`, `-`, `*` and `/`, plus `%`, the **remainder** (also called *modulo*). `17 % 5` is `2`, because 17 = 3 × 5 + 2.

The remainder is handy far more often than you might expect:

- `n % 2 == 0` tells you whether `n` is even.
- `n % 10` is the last digit of `n`, and `n / 10` drops that last digit.
- `minutes % 60` and `minutes / 60` split a time into hours and minutes.

```c
#include <stdio.h>

int main(void) {
    int total = 135;              /* minutes */
    int hours = total / 60;
    int minutes = total % 60;
    printf("%d minutes is %d h %d min\n", total, hours, minutes);

    int n = 4729;
    printf("last digit of %d is %d\n", n, n % 10);
    printf("without it: %d\n", n / 10);
    return 0;
}
```

There are also shortcuts for changing a variable: `x += 5` means `x = x + 5`, and `x++` adds one.

Things to try:

1. Change `total` to `59`, then `60`, then `61`.
2. What is `-7 % 3` in C? Run it and see (the sign follows the left-hand number).
3. Print the second-last digit of `n` using both `/` and `%`.

## Exercise

Read a number of seconds and print it as hours, minutes and seconds in the form `H:MM:SS`. For example `3725` is `1:02:05`. Hint: `%02d` prints a number with at least two digits, padding with a zero.

```input
3725
```

```c starter
#include <stdio.h>

int main(void) {
    int s;
    scanf("%d", &s);
    /* print it as H:MM:SS */
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    int s;
    scanf("%d", &s);
    printf("%d:%02d:%02d\n", s / 3600, s / 60 % 60, s % 60);
    return 0;
}
```

```tests
{"name": "an hour and a bit", "stdin": "3725\n", "expected": "1:02:05"}
{"name": "zero", "stdin": "0\n", "expected": "0:00:00"}
{"name": "a day minus one second", "stdin": "86399\n", "expected": "23:59:59"}
{"name": "exactly a minute", "stdin": "60\n", "expected": "0:01:00", "hidden": true}
```
