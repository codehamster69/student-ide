---
title: Variables and types
summary: Store whole numbers, decimals and characters, and print them.
---
A **variable** is a named box that holds a value. In C you must say what *type* of value goes in the box before you use it:

| Type | Holds | Example |
|---|---|---|
| `int` | whole numbers | `int age = 19;` |
| `double` | numbers with a decimal point | `double price = 49.5;` |
| `char` | a single character | `char grade = 'A';` |

To print a variable, `printf` needs a *format specifier* that matches its type: `%d` for `int`, `%f` for `double` (or `%.2f` for two decimals) and `%c` for `char`.

```c
#include <stdio.h>

int main(void) {
    int apples = 7;
    double kg = 1.25;
    char size = 'L';

    printf("%d apples weigh %.2f kg (size %c)\n", apples, kg, size);

    apples = apples + 3;   /* a variable can change */
    printf("Now there are %d apples\n", apples);
    return 0;
}
```

Things to try:

1. Print `kg` with `%f` instead of `%.2f`. How many decimals do you get?
2. Put a `double` into an `int`: `int whole = 3.99;` and print it. C does not round, it *cuts off* the decimals.
3. Divide two `int`s: `printf("%d\n", 7 / 2);`. Then try `7.0 / 2` with `%f`. Integer division throws the remainder away.

## Exercise

A rectangle is 12 units wide and 5 units tall. Store the width and height in `int` variables and print its area and perimeter like this:

```
area = 60
perimeter = 34
```

```c starter
#include <stdio.h>

int main(void) {
    int width = 12;
    int height = 5;
    /* print the area and the perimeter */
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    int width = 12;
    int height = 5;
    printf("area = %d\n", width * height);
    printf("perimeter = %d\n", 2 * (width + height));
    return 0;
}
```

```tests
{"name": "12 x 5", "stdin": "", "expected": "area = 60\nperimeter = 34"}
```
