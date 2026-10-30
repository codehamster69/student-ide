---
title: Templates
summary: Write a function or class once, for any type.
---
`std::vector<int>` and `std::vector<std::string>` are the same code used with different types. That code is a **template**. You can write your own: the compiler makes a separate version for each type you use it with.

```cpp
#include <iostream>
#include <string>
#include <vector>

template <typename T>
T largest(const std::vector<T> &v) {
    T best = v[0];
    for (const T &x : v) {
        if (best < x) best = x;      // works for any T that has <
    }
    return best;
}

template <typename A, typename B>
struct Pair {
    A first;
    B second;
    void show() const { std::cout << "(" << first << ", " << second << ")\n"; }
};

int main() {
    std::cout << largest(std::vector<int>{3, 9, 4}) << "\n";
    std::cout << largest(std::vector<double>{2.5, 1.5}) << "\n";
    std::cout << largest(std::vector<std::string>{"pear", "apple", "zebra"}) << "\n";

    Pair<std::string, int> p{"asha", 91};
    p.show();
    return 0;
}
```

- `template <typename T>` introduces a type parameter `T`. The compiler usually works out `T` from the arguments; you can also write it, as in `Pair<std::string, int>`.
- If a type doesn't support what the template uses (here `<`), you get a compile error, sometimes a long one. Read the first lines.
- Templates usually live entirely in header files, because the compiler needs the full code to make each version.

Things to try:

1. Call `largest` on an empty vector. Why is that a problem, and how would you guard against it?
2. Write `template <typename T> void swap_values(T &a, T &b)`.
3. Add a member function `swapped()` to `Pair` that returns a `Pair<B, A>`.

## Exercise

Write a class template `Stack<T>` with `push`, `pop` (removes the top), `top` (returns it), `empty` and `size`, built on a `std::vector<T>`. `main` uses it with both `int` and `std::string`: it reverses a list of numbers and a list of words.

```input
4
1 2 3 4
3
red green blue
```

```cpp starter
#include <iostream>
#include <string>
#include <vector>

// template <typename T> class Stack { ... };

template <typename T>
void reverse_print(int n) {
    Stack<T> s;
    for (int i = 0; i < n; i++) {
        T x;
        std::cin >> x;
        s.push(x);
    }
    std::cout << "size " << s.size() << ":";
    while (!s.empty()) {
        std::cout << " " << s.top();
        s.pop();
    }
    std::cout << "\n";
}

int main() {
    int n, m;
    std::cin >> n;
    reverse_print<int>(n);
    std::cin >> m;
    reverse_print<std::string>(m);
    return 0;
}
```

```cpp solution
#include <iostream>
#include <string>
#include <vector>

template <typename T>
class Stack {
public:
    void push(const T &x) { items_.push_back(x); }
    void pop() { items_.pop_back(); }
    const T &top() const { return items_.back(); }
    bool empty() const { return items_.empty(); }
    std::size_t size() const { return items_.size(); }
private:
    std::vector<T> items_;
};

template <typename T>
void reverse_print(int n) {
    Stack<T> s;
    for (int i = 0; i < n; i++) {
        T x;
        std::cin >> x;
        s.push(x);
    }
    std::cout << "size " << s.size() << ":";
    while (!s.empty()) {
        std::cout << " " << s.top();
        s.pop();
    }
    std::cout << "\n";
}

int main() {
    int n, m;
    std::cin >> n;
    reverse_print<int>(n);
    std::cin >> m;
    reverse_print<std::string>(m);
    return 0;
}
```

```tests
{"name": "numbers and words", "stdin": "4\n1 2 3 4\n3\nred green blue\n", "expected": "size 4: 4 3 2 1\nsize 3: blue green red"}
{"name": "single items", "stdin": "1\n9\n1\nz\n", "expected": "size 1: 9\nsize 1: z", "hidden": true}
```
