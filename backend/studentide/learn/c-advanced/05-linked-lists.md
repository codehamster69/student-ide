---
title: Linked lists
summary: Nodes that point to the next node, built with malloc.
---
An array keeps its elements side by side, so inserting in the middle means shifting everything after it. A **linked list** keeps each element in its own *node*, and each node points to the next one. Inserting is just changing a couple of pointers.

```c
#include <stdio.h>
#include <stdlib.h>

typedef struct Node {
    int value;
    struct Node *next;      /* NULL marks the end */
} Node;

Node *push_front(Node *head, int value) {
    Node *n = malloc(sizeof(Node));
    n->value = value;
    n->next = head;
    return n;               /* the new node is the new head */
}

void print_list(const Node *head) {
    for (const Node *p = head; p != NULL; p = p->next) {
        printf("%d -> ", p->value);
    }
    printf("NULL\n");
}

void free_list(Node *head) {
    while (head != NULL) {
        Node *next = head->next;   /* save it before freeing */
        free(head);
        head = next;
    }
}

int main(void) {
    Node *list = NULL;
    for (int i = 1; i <= 4; i++) {
        list = push_front(list, i * 10);
    }
    print_list(list);       /* 40 -> 30 -> 20 -> 10 -> NULL */
    free_list(list);
    return 0;
}
```

- `struct Node *next` inside `struct Node` is allowed because it is only a *pointer* to a node.
- `p->value` is short for `(*p).value`.
- In `free_list`, reading `head->next` *after* `free(head)` would be a use-after-free bug. That is why `next` is saved first.

Things to try:

1. Write `int length(const Node *head)`.
2. Write `push_back`, which walks to the last node and attaches the new one there.
3. Write a function that deletes the first node holding a given value.

## Exercise

Read `n` and then `n` whole numbers, and store them in a linked list **in input order** (add each one at the end). Then reverse the list *in place* by changing the `next` pointers (no second list, no array) and print it as `a -> b -> ... -> NULL`.

```input
4
1 2 3 4
```

```c starter
#include <stdio.h>
#include <stdlib.h>

typedef struct Node {
    int value;
    struct Node *next;
} Node;

Node *reverse(Node *head) {
    /* turn every next pointer around; return the new head */
    return head;
}

int main(void) {
    int n;
    scanf("%d", &n);
    Node *head = NULL, *tail = NULL;
    for (int i = 0; i < n; i++) {
        Node *node = malloc(sizeof(Node));
        scanf("%d", &node->value);
        node->next = NULL;
        if (tail == NULL) head = node; else tail->next = node;
        tail = node;
    }
    head = reverse(head);
    for (Node *p = head; p != NULL; p = p->next) {
        printf("%d -> ", p->value);
    }
    printf("NULL\n");
    return 0;
}
```

```c solution
#include <stdio.h>
#include <stdlib.h>

typedef struct Node {
    int value;
    struct Node *next;
} Node;

Node *reverse(Node *head) {
    Node *prev = NULL;
    while (head != NULL) {
        Node *next = head->next;
        head->next = prev;
        prev = head;
        head = next;
    }
    return prev;
}

int main(void) {
    int n;
    scanf("%d", &n);
    Node *head = NULL, *tail = NULL;
    for (int i = 0; i < n; i++) {
        Node *node = malloc(sizeof(Node));
        scanf("%d", &node->value);
        node->next = NULL;
        if (tail == NULL) head = node; else tail->next = node;
        tail = node;
    }
    head = reverse(head);
    for (Node *p = head; p != NULL; p = p->next) {
        printf("%d -> ", p->value);
    }
    printf("NULL\n");
    return 0;
}
```

```tests
{"name": "1 2 3 4", "stdin": "4\n1 2 3 4\n", "expected": "4 -> 3 -> 2 -> 1 -> NULL"}
{"name": "one", "stdin": "1\n5\n", "expected": "5 -> NULL"}
{"name": "empty", "stdin": "0\n", "expected": "NULL"}
{"name": "two", "stdin": "2\n8 9\n", "expected": "9 -> 8 -> NULL", "hidden": true}
```
