---
title: typedef, enum and union
summary: Name your own types, give numbers names, and share memory between fields.
---
**`typedef`** gives a type a new name, so `struct point` can be written just `Point`:

```c
#include <stdio.h>

typedef struct {
    double x, y;
} Point;

typedef enum { RED, GREEN, BLUE } Color;   /* RED = 0, GREEN = 1, BLUE = 2 */

const char *color_name(Color c) {
    switch (c) {
        case RED:   return "red";
        case GREEN: return "green";
        case BLUE:  return "blue";
    }
    return "?";
}

int main(void) {
    Point p = {1.5, -2.0};
    Color c = GREEN;
    printf("(%.1f, %.1f) is %s\n", p.x, p.y, color_name(c));
    printf("BLUE is stored as %d\n", BLUE);
    return 0;
}
```

- An **`enum`** is a set of named integer constants. It makes code read as words (`state == RUNNING`) instead of magic numbers (`state == 2`).
- **`switch`** jumps to the matching `case`. Without `return` or `break`, it *falls through* into the next case. Try removing a `return` above.

A **`union`** looks like a struct, but all its members share the **same** memory, so only one is meaningful at a time. Unions save space when a value can be one of several kinds, usually together with an enum saying which:

```c
#include <stdio.h>

typedef enum { INT, REAL } Kind;
typedef struct {
    Kind kind;
    union { int i; double d; } as;
} Value;

void show(Value v) {
    if (v.kind == INT) printf("int %d\n", v.as.i);
    else printf("real %.2f\n", v.as.d);
}

int main(void) {
    Value a = {INT, {.i = 7}};
    Value b = {REAL, {.d = 2.5}};
    show(a);
    show(b);
    printf("sizeof(Value) = %zu\n", sizeof(Value));
    return 0;
}
```

Things to try:

1. Add `YELLOW` to the enum and to `color_name`. What does the compiler say if you forget the `case`? (Try compiling with all warnings in your head: a missing case is a classic bug.)
2. Set `a.as.d = 1.0` and then print `a.as.i`. The bytes are the same, the meaning is not.
3. Give an enum explicit values: `enum { LOW = 1, HIGH = 10 }`.

## Exercise

Each input line is a shape: `C r` (circle with radius r), `R w h` (rectangle) or `T b h` (triangle with base and height). The first line is how many shapes follow. Print the total area with two decimals. Use π = 3.14159265.

Store each shape as a struct with an `enum` for its kind (a union for the sizes is a nice extra).

```input
3
C 1
R 2 3
T 4 5
```

```c starter
#include <stdio.h>

typedef enum { CIRCLE, RECT, TRIANGLE } Kind;

typedef struct {
    Kind kind;
    double a, b;
} Shape;

double area(Shape s) {
    /* use a switch on s.kind */
    return 0;
}

int main(void) {
    int n;
    scanf("%d", &n);
    double total = 0;
    for (int i = 0; i < n; i++) {
        char k;
        Shape s = {CIRCLE, 0, 0};
        scanf(" %c", &k);
        /* fill s from the input and add its area */
    }
    printf("%.2f\n", total);
    return 0;
}
```

```c solution
#include <stdio.h>

typedef enum { CIRCLE, RECT, TRIANGLE } Kind;

typedef struct {
    Kind kind;
    double a, b;
} Shape;

double area(Shape s) {
    switch (s.kind) {
        case CIRCLE:   return 3.14159265 * s.a * s.a;
        case RECT:     return s.a * s.b;
        case TRIANGLE: return s.a * s.b / 2;
    }
    return 0;
}

int main(void) {
    int n;
    scanf("%d", &n);
    double total = 0;
    for (int i = 0; i < n; i++) {
        char k;
        Shape s = {CIRCLE, 0, 0};
        scanf(" %c", &k);
        if (k == 'C') {
            scanf("%lf", &s.a);
        } else {
            s.kind = k == 'R' ? RECT : TRIANGLE;
            scanf("%lf %lf", &s.a, &s.b);
        }
        total += area(s);
    }
    printf("%.2f\n", total);
    return 0;
}
```

```tests
{"name": "one of each", "stdin": "3\nC 1\nR 2 3\nT 4 5\n", "expected": "19.14"}
{"name": "rectangle", "stdin": "1\nR 2.5 4\n", "expected": "10.00"}
{"name": "circles", "stdin": "2\nC 2\nC 0.5\n", "expected": "13.35", "hidden": true}
```
