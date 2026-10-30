---
title: Smart pointers
summary: unique_ptr and shared_ptr: heap memory that frees itself.
---
`new` and `delete` work in C++, but forgetting a `delete` leaks memory, and deleting twice crashes. **Smart pointers** (in `<memory>`) are objects that hold a pointer and delete it in their destructor, so ownership is clear and clean-up is automatic (RAII again).

```cpp
#include <iostream>
#include <memory>
#include <string>

struct Book {
    std::string title;
    explicit Book(std::string t) : title(std::move(t)) { std::cout << "+ " << title << "\n"; }
    ~Book() { std::cout << "- " << title << "\n"; }
};

int main() {
    {
        std::unique_ptr<Book> a = std::make_unique<Book>("Dune");   // one owner
        std::unique_ptr<Book> b = std::move(a);                     // ownership moves; a is now empty
        std::cout << (a ? "a owns it" : "a is empty") << ", b has " << b->title << "\n";
    }                                                               // Dune deleted here

    std::shared_ptr<Book> s1 = std::make_shared<Book>("Emma");      // shared ownership
    {
        std::shared_ptr<Book> s2 = s1;                              // a second owner
        std::cout << "owners: " << s1.use_count() << "\n";          // 2
    }
    std::cout << "owners: " << s1.use_count() << "\n";              // 1
    return 0;
}                                                                    // Emma deleted here
```

- **`std::unique_ptr<T>`**: exactly one owner. It can't be copied, only moved. Use this by default.
- **`std::shared_ptr<T>`**: shared ownership with a counter; the object is deleted when the last owner goes away. A bit slower; use it only when ownership is really shared.
- **`std::weak_ptr<T>`** watches a `shared_ptr` without owning it, which breaks reference cycles (two objects pointing at each other would otherwise never be freed).
- Create them with `std::make_unique` / `std::make_shared`, and almost never write `new` or `delete` yourself.

Things to try:

1. Try to copy a `unique_ptr`: `auto c = b;`. Read the error.
2. Return a `std::unique_ptr<Book>` from a function that creates a book.
3. Make two `shared_ptr` objects point at each other through members and watch the destructors never run. Fix it with `weak_ptr`.

## Exercise

Build a binary search tree out of `std::unique_ptr<Node>` children: insert the input numbers one by one (smaller to the left, larger or equal to the right), then print the numbers in sorted order (an in-order walk) and the tree's height (an empty tree has height 0, one node has height 1). No `new` or `delete`.

```input
7
50 30 70 20 40 60 80
```

```cpp starter
#include <algorithm>
#include <iostream>
#include <memory>

struct Node {
    int value;
    std::unique_ptr<Node> left, right;
    explicit Node(int v) : value(v) {}
};

void insert(std::unique_ptr<Node> &root, int v) {
    // if root is empty make a node, else go left or right
}

void in_order(const Node *n) {
}

int height(const Node *n) {
    return 0;
}

int main() {
    int k;
    std::cin >> k;
    std::unique_ptr<Node> root;
    for (int i = 0; i < k; i++) {
        int v;
        std::cin >> v;
        insert(root, v);
    }
    in_order(root.get());
    std::cout << "\nheight " << height(root.get()) << "\n";
    return 0;
}
```

```cpp solution
#include <algorithm>
#include <iostream>
#include <memory>

struct Node {
    int value;
    std::unique_ptr<Node> left, right;
    explicit Node(int v) : value(v) {}
};

void insert(std::unique_ptr<Node> &root, int v) {
    if (!root) {
        root = std::make_unique<Node>(v);
    } else if (v < root->value) {
        insert(root->left, v);
    } else {
        insert(root->right, v);
    }
}

void in_order(const Node *n) {
    if (!n) return;
    in_order(n->left.get());
    std::cout << n->value << " ";
    in_order(n->right.get());
}

int height(const Node *n) {
    return n ? 1 + std::max(height(n->left.get()), height(n->right.get())) : 0;
}

int main() {
    int k;
    std::cin >> k;
    std::unique_ptr<Node> root;
    for (int i = 0; i < k; i++) {
        int v;
        std::cin >> v;
        insert(root, v);
    }
    in_order(root.get());
    std::cout << "\nheight " << height(root.get()) << "\n";
    return 0;
}
```

```tests
{"name": "balanced", "stdin": "7\n50 30 70 20 40 60 80\n", "expected": "20 30 40 50 60 70 80\nheight 3"}
{"name": "a chain", "stdin": "4\n1 2 3 4\n", "expected": "1 2 3 4\nheight 4"}
{"name": "duplicates", "stdin": "3\n5 5 5\n", "expected": "5 5 5\nheight 3", "hidden": true}
```
