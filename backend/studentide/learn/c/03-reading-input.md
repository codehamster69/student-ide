---
title: Reading input
summary: Use scanf to read numbers the user types.
---
`scanf` is the opposite of `printf`: it *reads* values. It uses the same format specifiers, but each variable gets an `&` in front of it. The `&` gives `scanf` the variable's address so it can put the value there (the pointers lesson explains this properly).

```c
#include <stdio.h>

int main(void) {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d + %d = %d\n", a, b, a + b);
    return 0;
}
```

The **Input** box under the editor is what your program reads. Change the two numbers there and press **Run** again.

Things to try:

1. Remove the `&` before `a`. The compiler warns you, and the program may crash. That `&` matters.
2. Read a `double` with `%lf` (note: `lf` for `scanf`, plain `f` for `printf`).
3. Type a word instead of a number in the Input box. What does the program print?

## Exercise

Read a temperature in Celsius (a whole number) and print it in Fahrenheit with one decimal place. The formula is `F = C * 9 / 5 + 32`. Be careful: with only `int`s, `9 / 5` is `1`.

Input `100` should print `212.0`, and `-40` should print `-40.0`.

```input
100
```

```c starter
#include <stdio.h>

int main(void) {
    int c;
    scanf("%d", &c);
    /* print the temperature in Fahrenheit */
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    int c;
    scanf("%d", &c);
    printf("%.1f\n", c * 9.0 / 5 + 32);
    return 0;
}
```

```tests
{"name": "boiling", "stdin": "100\n", "expected": "212.0"}
{"name": "body temperature", "stdin": "37\n", "expected": "98.6"}
{"name": "where the scales meet", "stdin": "-40\n", "expected": "-40.0"}
{"name": "freezing", "stdin": "0\n", "expected": "32.0", "hidden": true}
```
