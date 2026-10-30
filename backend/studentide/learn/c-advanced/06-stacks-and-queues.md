---
title: Stacks and queues
summary: Two small data structures that power undo buttons, parsers and print queues.
---
A **stack** is last in, first out: you `push` onto the top and `pop` from the top, like a pile of plates. A **queue** is first in, first out: you add at the back and take from the front, like a line at a counter.

Both are easy to build on an array:

```c
#include <stdio.h>

#define CAP 100

int stack[CAP], top = 0;          /* top = how many items are on the stack */

void push(int x) { stack[top++] = x; }
int pop(void)    { return stack[--top]; }
int empty(void)  { return top == 0; }

int queue[CAP], head = 0, tail = 0;   /* items live in queue[head..tail-1] */

void enqueue(int x) { queue[tail++] = x; }
int dequeue(void)   { return queue[head++]; }

int main(void) {
    for (int i = 1; i <= 3; i++) {
        push(i);
        enqueue(i);
    }
    printf("stack pops: ");
    while (!empty()) printf("%d ", pop());       /* 3 2 1 */
    printf("\nqueue gives: ");
    while (head < tail) printf("%d ", dequeue()); /* 1 2 3 */
    printf("\n");
    return 0;
}
```

- Popping an empty stack reads `stack[-1]`, which is outside the array. Real code checks `empty()` first, and checks for a full stack before pushing.
- This simple queue can only take `CAP` items in total. A *circular* queue wraps around with `tail = (tail + 1) % CAP` so freed slots get reused.

Stacks are how programs check that brackets match: push every opening bracket, and every closing bracket must match the one on top.

Things to try:

1. Add checks so `push` on a full stack and `pop` on an empty one print an error instead.
2. Turn the queue into a circular one with `% CAP`.
3. Use the stack to print a word backwards.

## Exercise

Read one line of brackets `()[]{}` (at most 200 characters) and print `balanced` if every bracket is closed by the matching kind in the right order, otherwise `not balanced`. So `{[()]}` is balanced, `([)]` and `((` are not.

```input
{[()()]}
```

```c starter
#include <stdio.h>

int main(void) {
    char s[256];
    scanf("%255s", s);
    /* push opening brackets; each closing bracket must match the top */
    return 0;
}
```

```c solution
#include <stdio.h>

int main(void) {
    char s[256];
    char stack[256];
    int top = 0, ok = 1;
    scanf("%255s", s);
    for (int i = 0; s[i] != '\0' && ok; i++) {
        char c = s[i];
        if (c == '(' || c == '[' || c == '{') {
            stack[top++] = c;
        } else {
            char want = c == ')' ? '(' : c == ']' ? '[' : '{';
            if (top == 0 || stack[top - 1] != want) {
                ok = 0;
            } else {
                top--;
            }
        }
    }
    printf(ok && top == 0 ? "balanced\n" : "not balanced\n");
    return 0;
}
```

```tests
{"name": "nested", "stdin": "{[()()]}\n", "expected": "balanced"}
{"name": "crossed", "stdin": "([)]\n", "expected": "not balanced"}
{"name": "left open", "stdin": "((\n", "expected": "not balanced"}
{"name": "closes too early", "stdin": "())(\n", "expected": "not balanced", "hidden": true}
```
