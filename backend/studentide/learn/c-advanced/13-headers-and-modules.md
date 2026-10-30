---
title: Headers, prototypes and programs in several files
summary: Declare before you use, split a program into .c and .h files, extern, static functions and include guards.
---
The compiler reads a file from top to bottom, so a function must be **declared** before it is called. A **prototype** is a declaration without a body: it tells the compiler the name, the parameter types and the return type, and the body can come later.

```c
#include <stdio.h>

int is_even(int n);   /* prototypes */
int is_odd(int n);

int main(void) {
    printf("%d %d\n", is_even(10), is_odd(7));
    return 0;
}

int is_even(int n) { return n == 0 ? 1 : is_odd(n - 1); }
int is_odd(int n)  { return n == 0 ? 0 : is_even(n - 1); }
```

Without the prototypes, `is_even` would call `is_odd` before the compiler has seen it.

Real programs are split into several `.c` files, each compiled on its own and then linked together. The prototypes a file offers to others go into a **header** (`.h`) file, which the other files `#include`:

```
/* stack.h */
#ifndef STACK_H          /* include guard: the contents are read only once */
#define STACK_H
void push(int x);
int pop(void);
extern int stack_size;   /* a global defined in stack.c */
#endif

/* stack.c */
#include "stack.h"
static int items[100];   /* static: private to stack.c */
int stack_size = 0;
void push(int x) { items[stack_size++] = x; }
int pop(void) { return items[--stack_size]; }

/* main.c */
#include <stdio.h>
#include "stack.h"
int main(void) { push(4); push(5); printf("%d\n", pop()); return 0; }
```

You would build it with `gcc main.c stack.c -o app`. Four rules to remember:

- `#include <...>` searches the system's headers; `#include "..."` searches your project first.
- Headers hold **declarations** (prototypes, `extern` variables, `struct` and `typedef` definitions). Function bodies and variable definitions go in `.c` files, or the linker will complain that something is defined twice.
- `extern int x;` says "x exists in some other file". Exactly one `.c` file defines it.
- `static` on a function or global makes it private to its file, so two files can each have their own `helper`.

The editor here holds one file, so the exercise keeps that layout inside it.

Things to try:

1. Delete the prototype for `is_odd`. Read the compiler's message.
2. Change a prototype to `int is_odd(double n);` and see what the compiler says.
3. Write the stack example as one file, with the "header" part at the top.

## Exercise

The program below calls `area` and `perimeter` before their bodies appear, and their bodies are missing. Add prototypes at the top, as a header would, and write both functions at the bottom for a rectangle of width `w` and height `h`. Print area and perimeter as the given `main` does.

```input
3 4
```

```c starter
#include <stdio.h>

int main(void) {
    int w, h;
    scanf("%d %d", &w, &h);
    printf("area %d\n", area(w, h));
    printf("perimeter %d\n", perimeter(w, h));
    return 0;
}
```

```c solution
#include <stdio.h>

int area(int w, int h);
int perimeter(int w, int h);

int main(void) {
    int w, h;
    scanf("%d %d", &w, &h);
    printf("area %d\n", area(w, h));
    printf("perimeter %d\n", perimeter(w, h));
    return 0;
}

int area(int w, int h) { return w * h; }
int perimeter(int w, int h) { return 2 * (w + h); }
```

```tests
{"name": "3 4", "stdin": "3 4\n", "expected": "area 12\nperimeter 14"}
{"name": "square", "stdin": "5 5\n", "expected": "area 25\nperimeter 20"}
{"name": "thin", "stdin": "1 10\n", "expected": "area 10\nperimeter 22", "hidden": true}
```
