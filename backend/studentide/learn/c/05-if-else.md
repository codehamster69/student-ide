---
title: Making decisions
summary: if, else if and else, and how to combine conditions.
---
`if` runs a block of code only when its condition is true. `else` runs when it is false, and `else if` lets you test several conditions in order: the first one that is true wins and the rest are skipped.

```c
#include <stdio.h>

int main(void) {
    int marks;
    scanf("%d", &marks);

    if (marks >= 90) {
        printf("Grade A\n");
    } else if (marks >= 75) {
        printf("Grade B\n");
    } else if (marks >= 40) {
        printf("Grade C\n");
    } else {
        printf("Try again\n");
    }
    return 0;
}
```

Comparisons: `==` (equal), `!=` (not equal), `<`, `<=`, `>`, `>=`. Combine them with `&&` (and), `||` (or) and `!` (not): `if (age >= 13 && age <= 19)`.

A classic mistake is writing `=` where you meant `==`. `if (x = 5)` *assigns* 5 to `x` and is always true. Try it.

Things to try:

1. Change the marks in the Input box to hit every branch.
2. Swap the order of the first two conditions. Why does 95 now give the wrong grade?
3. Add a check that prints `Invalid` for marks below 0 or above 100.

## Exercise

Read a year and print `leap` if it is a leap year, otherwise `not leap`. A year is a leap year if it is divisible by 4, except years divisible by 100, which are leap years only if they are also divisible by 400. So 2024 and 2000 are leap years, 1900 and 2023 are not.

```input
2024
```

```c starter
#include <stdio.h>

int main(void) {
    int year;
    scanf("%d", &year);
    /* print leap or not leap */
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    int year;
    scanf("%d", &year);
    if ((year % 4 == 0 && year % 100 != 0) || year % 400 == 0) {
        printf("leap\n");
    } else {
        printf("not leap\n");
    }
    return 0;
}
```

```tests
{"name": "2024", "stdin": "2024\n", "expected": "leap"}
{"name": "2023", "stdin": "2023\n", "expected": "not leap"}
{"name": "1900", "stdin": "1900\n", "expected": "not leap"}
{"name": "2000", "stdin": "2000\n", "expected": "leap"}
{"name": "2100", "stdin": "2100\n", "expected": "not leap", "hidden": true}
```
