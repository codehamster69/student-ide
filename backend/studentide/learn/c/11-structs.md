---
title: Structs
summary: Group related values of different types into one record.
---
A **struct** bundles several values, possibly of different types, into one record. Each value is a *member*, reached with a dot.

```c
#include <stdio.h>

struct student {
    char name[30];
    int roll;
    double cgpa;
};

int main(void) {
    struct student s = {"Meera", 42, 8.7};
    printf("%s (roll %d) has CGPA %.1f\n", s.name, s.roll, s.cgpa);

    s.cgpa = 9.1;
    printf("updated: %.1f\n", s.cgpa);
    return 0;
}
```

Structs can go into arrays, be passed to functions and be returned from them. When you have a *pointer* to a struct, use `->` instead of the dot: `p->cgpa` means `(*p).cgpa`.

```c
#include <stdio.h>

struct point {
    int x, y;
};

void move(struct point *p, int dx, int dy) {
    p->x += dx;
    p->y += dy;
}

int main(void) {
    struct point pts[3] = {{0, 0}, {2, 5}, {-1, 3}};
    move(&pts[1], 10, 10);
    for (int i = 0; i < 3; i++) {
        printf("(%d, %d)\n", pts[i].x, pts[i].y);
    }
    return 0;
}
```

Things to try:

1. Add a `char section;` member to `student` and print it.
2. Write a function `double distance2(struct point a, struct point b)` that returns the squared distance.
3. `typedef struct point point;` lets you write `point` instead of `struct point`. Try it.

## Exercise

The input has a count `n` (at most 50) and then `n` lines, each a name (one word) and marks. Print the name and marks of the student with the highest marks (the first one if there is a tie), separated by a space.

```input
3
Asha 78
Ravi 91
Neel 85
```

```c starter
#include <stdio.h>

struct entry {
    char name[32];
    int marks;
};

int main(void) {
    int n;
    struct entry e[50];
    scanf("%d", &n);
    for (int i = 0; i < n; i++) {
        scanf("%31s %d", e[i].name, &e[i].marks);
    }
    /* print the top student */
    return 0;
}
```

```c solution
#include <stdio.h>

struct entry {
    char name[32];
    int marks;
};

int main(void) {
    int n;
    struct entry e[50];
    scanf("%d", &n);
    for (int i = 0; i < n; i++) {
        scanf("%31s %d", e[i].name, &e[i].marks);
    }
    int best = 0;
    for (int i = 1; i < n; i++) {
        if (e[i].marks > e[best].marks) {
            best = i;
        }
    }
    printf("%s %d\n", e[best].name, e[best].marks);
    return 0;
}
```

```tests
{"name": "three students", "stdin": "3\nAsha 78\nRavi 91\nNeel 85\n", "expected": "Ravi 91"}
{"name": "first is best", "stdin": "2\nZoya 99\nAmit 10\n", "expected": "Zoya 99"}
{"name": "tie keeps the first", "stdin": "3\nA 50\nB 70\nC 70\n", "expected": "B 70", "hidden": true}
```
