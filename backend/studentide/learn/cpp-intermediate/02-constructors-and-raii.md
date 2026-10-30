---
title: Constructors, destructors and RAII
summary: Objects that clean up after themselves when they go out of scope.
---
A **destructor** (`~ClassName()`) runs automatically when an object's life ends: at the closing `}` of the block it was made in, or when it is deleted. C++ programs rely on this a lot: an object takes a resource in its constructor and gives it back in its destructor. This idea is called **RAII** ("resource acquisition is initialisation"), and it is why you rarely see `free` in good C++.

```cpp
#include <iostream>
#include <string>

class Noisy {
public:
    Noisy(std::string name) : name_(name) { std::cout << "make " << name_ << "\n"; }
    ~Noisy() { std::cout << "destroy " << name_ << "\n"; }
private:
    std::string name_;
};

int main() {
    Noisy a("a");
    {
        Noisy b("b");
        Noisy c("c");
        std::cout << "end of inner block\n";
    }                                   // c then b destroyed here (reverse order)
    std::cout << "end of main\n";
    return 0;
}                                       // a destroyed here
```

The standard library is built this way: a `std::vector` or `std::string` frees its memory in its destructor, `std::ifstream` closes its file, and `std::lock_guard` releases a lock. You get clean-up for free, even when a function returns early or an exception is thrown.

A class can have several constructors, and a constructor can have default values:

```cpp
#include <iostream>

class Counter {
public:
    Counter() : value_(0) {}                     // default constructor
    explicit Counter(int start) : value_(start) {}
    void tick() { ++value_; }
    int value() const { return value_; }
private:
    int value_;
};

int main() {
    Counter a, b(10);
    a.tick(); b.tick(); b.tick();
    std::cout << a.value() << " " << b.value() << "\n";   // 1 12
    return 0;
}
```

`explicit` stops the compiler from silently turning an `int` into a `Counter`.

Things to try:

1. Make a `Noisy` inside a loop that runs 3 times. When is each one destroyed?
2. Put `Noisy` objects into a `std::vector` and watch the messages.
3. Add a `return` in the middle of the inner block. Do the destructors still run?

## Exercise

Write a class `ScopeLogger` whose constructor prints `enter <name>` and whose destructor prints `leave <name>`, indented by two spaces per level of nesting (keep the current depth in a `static int` member). `main` builds nested scopes from the input: `{name` opens a scope, `}` closes the latest one.

```input
6
{main
{load
}
{run
}
}
```

```cpp starter
#include <iostream>
#include <memory>
#include <string>
#include <vector>

class ScopeLogger {
public:
    ScopeLogger(const std::string &name) {}
};

int main() {
    int n;
    std::cin >> n;
    std::vector<std::unique_ptr<ScopeLogger>> open;
    for (int i = 0; i < n; i++) {
        std::string tok;
        std::cin >> tok;
        if (tok[0] == '{') open.push_back(std::make_unique<ScopeLogger>(tok.substr(1)));
        else open.pop_back();             // destroys the newest logger
    }
    while (!open.empty()) open.pop_back();   // close what is still open, newest first
    return 0;
}
```

```cpp solution
#include <iostream>
#include <memory>
#include <string>
#include <vector>

class ScopeLogger {
public:
    ScopeLogger(const std::string &name) : name_(name) {
        std::cout << std::string(2 * depth_, ' ') << "enter " << name_ << "\n";
        ++depth_;
    }
    ~ScopeLogger() {
        --depth_;
        std::cout << std::string(2 * depth_, ' ') << "leave " << name_ << "\n";
    }
private:
    std::string name_;
    static int depth_;
};

int ScopeLogger::depth_ = 0;

int main() {
    int n;
    std::cin >> n;
    std::vector<std::unique_ptr<ScopeLogger>> open;
    for (int i = 0; i < n; i++) {
        std::string tok;
        std::cin >> tok;
        if (tok[0] == '{') open.push_back(std::make_unique<ScopeLogger>(tok.substr(1)));
        else open.pop_back();             // destroys the newest logger
    }
    while (!open.empty()) open.pop_back();   // close what is still open, newest first
    return 0;
}
```

```tests
{"name": "example", "stdin": "6\n{main\n{load\n}\n{run\n}\n}\n", "expected": "enter main\n  enter load\n  leave load\n  enter run\n  leave run\nleave main"}
{"name": "left open", "stdin": "2\n{a\n{b\n", "expected": "enter a\n  enter b\n  leave b\nleave a", "hidden": true}
```
