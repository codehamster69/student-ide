---
title: Loops
summary: Repeat code with for and while.
---
A **loop** runs the same block again and again. A `for` loop is best when you know how many times to repeat:

```c
#include <stdio.h>

int main(void) {
    for (int i = 1; i <= 5; i++) {
        printf("%d squared is %d\n", i, i * i);
    }
    return 0;
}
```

The three parts inside `for ( ; ; )` are: where to start (`int i = 1`), when to keep going (`i <= 5`) and what to do after each round (`i++`).

A `while` loop keeps going as long as its condition is true. It suits cases where you don't know the count in advance, such as taking a number apart digit by digit:

```c
#include <stdio.h>

int main(void) {
    int n = 4729, digits = 0;
    while (n > 0) {
        n = n / 10;
        digits++;
    }
    printf("%d digits\n", digits);
    return 0;
}
```

Use **Try it** on either example to load it into the editor. `break` leaves a loop early, and `continue` skips to the next round.

Things to try:

1. Make the `for` loop count down from 10 to 1.
2. Print only the even numbers from 1 to 20 (two ways: change the step, or use `%` and `continue`).
3. Change `i <= 5` to `i > 0` in the first example. What happens? (The runner stops programs that run too long.)

## Exercise

Read a whole number `n` and print the sum of its digits. For `4729` that is 4 + 7 + 2 + 9 = `22`.

```input
4729
```

```c starter
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    int sum = 0;
    /* add up the digits of n */
    printf("%d\n", sum);
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    int sum = 0;
    while (n > 0) {
        sum += n % 10;
        n /= 10;
    }
    printf("%d\n", sum);
    return 0;
}
```

```tests
{"name": "4729", "stdin": "4729\n", "expected": "22"}
{"name": "one digit", "stdin": "7\n", "expected": "7"}
{"name": "with zeros", "stdin": "1005\n", "expected": "6"}
{"name": "big", "stdin": "999999999\n", "expected": "81", "hidden": true}
```
