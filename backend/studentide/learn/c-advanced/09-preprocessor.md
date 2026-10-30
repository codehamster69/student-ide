---
title: The preprocessor, const and static
summary: #define, macros and their traps, const, and static variables.
---
Before the compiler sees your code, the **preprocessor** runs. Every line starting with `#` is for it: `#include` pastes in a header file, and `#define` replaces text.

```c
#include <stdio.h>

#define SIZE 5
#define SQUARE(x) ((x) * (x))
#define BAD_SQUARE(x) x * x

int main(void) {
    int a[SIZE];
    for (int i = 0; i < SIZE; i++) a[i] = SQUARE(i);
    printf("%d %d\n", a[4], SQUARE(2 + 1));     /* 16 9 */
    printf("%d\n", BAD_SQUARE(2 + 1));           /* 2 + 1 * 2 + 1 = 5! */
#ifdef DEBUG
    printf("debug build\n");
#endif
    return 0;
}
```

- A macro is plain text substitution, not a function. That is why `SQUARE` wraps every use of `x` and the whole result in brackets, and why `SQUARE(i++)` is a bug (it increments twice).
- `#ifdef` / `#endif` keeps or drops code before compiling. Add `#define DEBUG` at the top and run again.

Two keywords that are not the preprocessor but are often met at the same time:

```c
#include <stdio.h>

int next_id(void) {
    static int counter = 0;   /* created once, keeps its value between calls */
    return ++counter;
}

int main(void) {
    const double PI = 3.14159;   /* can't be changed after this line */
    printf("%d %d %d\n", next_id(), next_id(), next_id());
    printf("%.2f\n", PI * 2);
    return 0;
}
```

- `const` makes a variable read-only. Try `PI = 3;` and read the compiler's error.
- A `static` variable inside a function lives for the whole program, so it remembers its value. A `static` function or global is visible only in its own file.

Things to try:

1. Write `#define MAX(a, b) ((a) > (b) ? (a) : (b))` and find an argument that is evaluated twice.
2. Remove `static` from `counter`. What does `next_id` return now?
3. Use `#define` to switch the program between two messages.

## Exercise

Complete `ABS` and `CLAMP` so the program prints the right values. Watch the brackets: the tests pass expressions like `a - b` to the macros.

`CLAMP(x, lo, hi)` is `lo` if `x < lo`, `hi` if `x > hi`, otherwise `x`.

```input
3 10
```

```c starter
#include <stdio.h>

#define ABS(x) 0
#define CLAMP(x, lo, hi) 0

int main(void) {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d %d\n", ABS(a - b), ABS(b - a));
    printf("%d %d %d\n", CLAMP(a - b, 0, 5), CLAMP(a + b, 0, 5), CLAMP(a, 0, 5));
    return 0;
}
```

```c solution
#include <stdio.h>

#define ABS(x) ((x) < 0 ? -(x) : (x))
#define CLAMP(x, lo, hi) ((x) < (lo) ? (lo) : (x) > (hi) ? (hi) : (x))

int main(void) {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d %d\n", ABS(a - b), ABS(b - a));
    printf("%d %d %d\n", CLAMP(a - b, 0, 5), CLAMP(a + b, 0, 5), CLAMP(a, 0, 5));
    return 0;
}
```

```tests
{"name": "3 10", "stdin": "3 10\n", "expected": "7 7\n0 5 3"}
{"name": "equal", "stdin": "4 4\n", "expected": "0 0\n0 5 4"}
{"name": "negative", "stdin": "-2 1\n", "expected": "3 3\n0 0 0", "hidden": true}
```
