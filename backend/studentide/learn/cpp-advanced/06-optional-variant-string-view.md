---
title: optional, variant and string_view
summary: A value that may be missing, a value that is one of several types, and looking at text without copying it.
---
C++17 added three small types that make everyday code safer.

`std::optional<T>` holds either a `T` or nothing. Return it from a function that may fail, instead of a magic value like `-1` or a separate `bool`. Test it like a `bool`, read it with `*` or `.value()`, or use `.value_or(fallback)`.

```cpp
#include <iostream>
#include <optional>
#include <string>

std::optional<int> parse_int(const std::string& s) {
    try {
        size_t used;
        int v = std::stoi(s, &used);
        if (used != s.size()) return std::nullopt;   // trailing junk
        return v;
    } catch (...) {
        return std::nullopt;
    }
}

int main() {
    for (std::string s : {"42", "4x", "-7", "abc"}) {
        auto v = parse_int(s);
        if (v) std::cout << s << " -> " << *v << "\n";
        else std::cout << s << " is not a number\n";
    }
    std::cout << parse_int("oops").value_or(0) << "\n";
    return 0;
}
```

`std::variant<A, B, C>` holds exactly one value whose type is one of `A`, `B` or `C`. It is a type-safe `union`: it knows which type it holds. `std::holds_alternative<T>(v)` asks, `std::get<T>(v)` reads (and throws if it is the wrong type), and `std::visit` runs a function on whatever is inside.

```cpp
#include <iostream>
#include <string>
#include <variant>
#include <vector>

using Value = std::variant<int, double, std::string>;

int main() {
    std::vector<Value> row = {3, 2.5, std::string("pen")};
    for (const Value& v : row) {
        std::visit([](const auto& x) { std::cout << x << " "; }, v);
    }
    std::cout << "\n";
    if (std::holds_alternative<std::string>(row[2])) std::cout << std::get<std::string>(row[2]).size() << "\n";
    return 0;
}
```

`std::string_view` is a read-only window onto characters stored somewhere else. Passing or slicing one copies nothing, which makes it a good parameter type for functions that only read text. The catch: it does not own the text, so it must not outlive the string it looks at.

```cpp
#include <iostream>
#include <string>
#include <string_view>

bool starts_with(std::string_view s, std::string_view prefix) {
    return s.substr(0, prefix.size()) == prefix;   // substr on a view copies nothing
}

int main() {
    std::string roll = "PG25CS07";
    std::cout << starts_with(roll, "PG") << starts_with("UG24", "PG") << "\n";
    // std::string_view bad = std::string("temp");   // dangles: the string dies at the ;
    return 0;
}
```

Things to try:

1. Call `.value()` on an empty optional. What happens?
2. Call `std::get<int>(row[1])`. Read the exception.
3. Add `bool` to the variant and a `true` to the row. What does `visit` print?

## Exercise

Each input line is a command: `push N` adds a number to a stack, `pop` removes the top one, and `top` prints it. Write `std::optional<int> top_of(const std::vector<int>&)` and `std::optional<int> pop_from(std::vector<int>&)`, which return nothing when the stack is empty. For `pop` print the removed number and for `top` print the top number, or `empty` when there is none.

```input
push 3
push 8
top
pop
pop
pop
```

```cpp starter
#include <iostream>
#include <optional>
#include <string>
#include <vector>

int main() {
    std::vector<int> stack;
    std::string cmd;
    while (std::cin >> cmd) {
        if (cmd == "push") {
            int x;
            std::cin >> x;
            stack.push_back(x);
        }
    }
    return 0;
}
```

```cpp solution
#include <iostream>
#include <optional>
#include <string>
#include <vector>

std::optional<int> top_of(const std::vector<int>& s) {
    if (s.empty()) return std::nullopt;
    return s.back();
}

std::optional<int> pop_from(std::vector<int>& s) {
    auto t = top_of(s);
    if (t) s.pop_back();
    return t;
}

void show(std::optional<int> v) {
    if (v) std::cout << *v << "\n";
    else std::cout << "empty\n";
}

int main() {
    std::vector<int> stack;
    std::string cmd;
    while (std::cin >> cmd) {
        if (cmd == "push") {
            int x;
            std::cin >> x;
            stack.push_back(x);
        } else if (cmd == "pop") {
            show(pop_from(stack));
        } else if (cmd == "top") {
            show(top_of(stack));
        }
    }
    return 0;
}
```

```tests
{"name": "example", "stdin": "push 3\npush 8\ntop\npop\npop\npop\n", "expected": "8\n8\n3\nempty"}
{"name": "empty top", "stdin": "top\npush 1\ntop\n", "expected": "empty\n1"}
{"name": "zero", "stdin": "push 0\npop\ntop\n", "expected": "0\nempty", "hidden": true}
```
