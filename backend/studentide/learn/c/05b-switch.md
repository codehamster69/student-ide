---
title: switch and the ?: operator
summary: Choose between many fixed cases with switch, and pick a value in one line with ?:.
---
When you compare one value against many constants, `switch` is tidier than a long `if`/`else if` chain. Execution jumps to the matching `case` and runs until a `break`. If nothing matches it runs `default`.

```c
#include <stdio.h>

int main(void) {
    int day;
    scanf("%d", &day);
    switch (day) {
        case 1: printf("Monday\n"); break;
        case 2: printf("Tuesday\n"); break;
        case 3: printf("Wednesday\n"); break;
        case 6:
        case 7: printf("Weekend\n"); break;   /* 6 falls through to 7 */
        default: printf("Some other day\n");
    }
    return 0;
}
```

Forgetting `break` is the classic `switch` bug: the code "falls through" into the next case. Sometimes that is what you want, as with 6 and 7 above. Case labels must be constants (`case 'a':` or `case 3:`), not ranges or variables.

The **conditional operator** `condition ? a : b` gives `a` if the condition is true and `b` otherwise. It is handy for small choices:

```c
#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    printf("%d is %s\n", n, n % 2 == 0 ? "even" : "odd");
    int abs_n = n < 0 ? -n : n;
    printf("absolute value: %d\n", abs_n);
    return 0;
}
```

```input
3
```

Things to try:

1. Remove the `break` after Monday and enter 1. What prints?
2. Add a `case` for every day of the week.
3. Rewrite the `?:` line with `if`/`else`. Which is easier to read?

## Exercise

Build a tiny calculator. Read an operator character and two integers, like `+ 3 4`, and print the result. Support `+`, `-`, `*` and `/` (integer division). Print `error` when dividing by zero and `unknown` for any other operator. Read the operator with `scanf(" %c", &op)`: the space skips any whitespace before it.

```input
+ 3 4
```

```c starter
#include <stdio.h>

int main(void) {
    char op;
    int a, b;
    scanf(" %c %d %d", &op, &a, &b);
    /* use a switch on op */
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    char op;
    int a, b;
    scanf(" %c %d %d", &op, &a, &b);
    switch (op) {
        case '+': printf("%d\n", a + b); break;
        case '-': printf("%d\n", a - b); break;
        case '*': printf("%d\n", a * b); break;
        case '/':
            if (b == 0) printf("error\n");
            else printf("%d\n", a / b);
            break;
        default: printf("unknown\n");
    }
    return 0;
}
```

```tests
{"name": "add", "stdin": "+ 3 4\n", "expected": "7"}
{"name": "multiply", "stdin": "* 6 7\n", "expected": "42"}
{"name": "divide by zero", "stdin": "/ 5 0\n", "expected": "error"}
{"name": "unknown", "stdin": "% 5 2\n", "expected": "unknown"}
{"name": "subtract", "stdin": "- 2 9\n", "expected": "-7", "hidden": true}
{"name": "divide", "stdin": "/ 17 5\n", "expected": "3", "hidden": true}
```
