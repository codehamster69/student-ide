---
title: Functions with any number of arguments
summary: How printf takes as many arguments as you like, and writing your own with stdarg.h.
---
`printf` accepts any number of arguments after its format string. You can write such **variadic** functions yourself with the macros in `<stdarg.h>`:

- `...` at the end of the parameter list means "and any number of extra arguments".
- `va_list args;` holds your place in the extra arguments.
- `va_start(args, last)` starts after the last named parameter.
- `va_arg(args, type)` gets the next argument, which you say must be of type `type`.
- `va_end(args)` cleans up.

```c
#include <stdarg.h>
#include <stdio.h>

double average(int count, ...) {
    va_list args;
    va_start(args, count);
    double sum = 0;
    for (int i = 0; i < count; i++) sum += va_arg(args, int);
    va_end(args);
    return count ? sum / count : 0;
}

int main(void) {
    printf("%.2f\n", average(3, 4, 5, 9));
    printf("%.2f\n", average(2, 10, 11));
    return 0;
}
```

The function cannot find out by itself how many extra arguments there are or what types they have. You have to tell it, as `count` does here and as `printf`'s format string does with each `%d` or `%s`. Getting this wrong is undefined behaviour: `average(3, 4, 5)` reads a third argument that is not there, and `printf("%d", 2.5)` reads a `double` as an `int`.

Small types are promoted when passed through `...`: `char` and `short` arrive as `int`, and `float` arrives as `double`. So you write `va_arg(args, int)` for a `char` and `va_arg(args, double)` for a `float`.

Things to try:

1. Call `average(4, 4, 5, 9)` with only three numbers after the count. What prints?
2. Write `void print_all(const char *label, int count, ...)` that prints the label and then each number.
3. Pass `2.5` to `average`. Why is the result wrong?

## Exercise

Write `int max_of(int count, ...)`, which returns the largest of its `count` integer arguments (`count` is at least 1). The given `main` calls it a few times with numbers from the input.

```input
4 9 2 7
```

```c starter
#include <stdarg.h>
#include <stdio.h>

int max_of(int count, ...) {
    return 0;
}

int main(void) {
    int a, b, c, d;
    scanf("%d %d %d %d", &a, &b, &c, &d);
    printf("%d\n", max_of(1, a));
    printf("%d\n", max_of(2, a, b));
    printf("%d\n", max_of(4, a, b, c, d));
    return 0;
}
```

```c solution
#include <stdarg.h>
#include <stdio.h>

int max_of(int count, ...) {
    va_list args;
    va_start(args, count);
    int best = va_arg(args, int);
    for (int i = 1; i < count; i++) {
        int x = va_arg(args, int);
        if (x > best) best = x;
    }
    va_end(args);
    return best;
}

int main(void) {
    int a, b, c, d;
    scanf("%d %d %d %d", &a, &b, &c, &d);
    printf("%d\n", max_of(1, a));
    printf("%d\n", max_of(2, a, b));
    printf("%d\n", max_of(4, a, b, c, d));
    return 0;
}
```

```tests
{"name": "example", "stdin": "4 9 2 7\n", "expected": "4\n9\n9"}
{"name": "negatives", "stdin": "-5 -2 -9 -1\n", "expected": "-5\n-2\n-1"}
{"name": "last is biggest", "stdin": "1 2 3 4\n", "expected": "1\n2\n4", "hidden": true}
```
