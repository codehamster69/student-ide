---
title: Copying and moving
summary: Copy constructors, move constructors, std::move, and the rule of five.
---
When an object is passed or returned by value, C++ either **copies** it or, if the original is about to disappear anyway, **moves** it: the new object steals the old one's resources (say, a big heap buffer) instead of duplicating them. Moving a vector of a million elements is a few pointer swaps; copying it is a million copies.

```cpp
#include <iostream>
#include <string>
#include <utility>
#include <vector>

class Buffer {
public:
    explicit Buffer(std::size_t n) : data_(n, 0) { std::cout << "make " << n << "\n"; }
    Buffer(const Buffer &other) : data_(other.data_) {              // copy constructor
        std::cout << "copy " << data_.size() << "\n";
    }
    Buffer(Buffer &&other) noexcept : data_(std::move(other.data_)) {   // move constructor
        std::cout << "move " << data_.size() << "\n";
    }
    std::size_t size() const { return data_.size(); }
private:
    std::vector<int> data_;
};

Buffer make_big() {
    Buffer b(1000);
    return b;                  // moved (or the copy is skipped entirely)
}

int main() {
    Buffer a(10);
    Buffer b = a;              // copy: a is still needed
    Buffer c = std::move(a);   // move: we promise not to use a's contents again
    Buffer d = make_big();
    std::cout << a.size() << " " << b.size() << " " << c.size() << " " << d.size() << "\n";
    return 0;
}
```

- `Buffer &&` is an *rvalue reference*: it binds to temporaries and to things wrapped in `std::move`. `std::move` doesn't move anything itself; it just marks the object as "you may steal from this".
- After a move, the old object is valid but unspecified (here `a` is empty). Don't rely on its value.
- **Rule of zero**: if your members (vector, string, unique_ptr) already manage themselves, write none of these functions and the compiler's defaults do the right thing. **Rule of five**: if you write a destructor, copy or move operation, think about all five.
- Mark move constructors `noexcept`, or `std::vector` will copy instead of move when it grows.

Things to try:

1. Remove the move constructor. What does `Buffer c = std::move(a)` print now?
2. Push `Buffer` objects into a `std::vector` and watch what happens as it grows (with and without `noexcept`).
3. Write `void take(Buffer b)` and call it with `a` and with `std::move(a)`.

## Exercise

Count how the program's objects travel. Complete `Tracker`'s copy and move constructors so that they increase the static counters `copies` and `moves`, then fill in the blanks in `main` so it does **exactly one copy and two moves**: copy `a` into the vector, then move `b` and `c` into it. The vector has room reserved, so it never moves things by itself. The program prints the counters and the names.

```input
alpha beta gamma
```

```cpp starter
#include <iostream>
#include <string>
#include <utility>
#include <vector>

struct Tracker {
    static int copies, moves;
    std::string name;
    explicit Tracker(std::string n) : name(std::move(n)) {}
    Tracker(const Tracker &o) : name(o.name) {}
    Tracker(Tracker &&o) noexcept : name(std::move(o.name)) {}
};
int Tracker::copies = 0, Tracker::moves = 0;

int main() {
    std::string x, y, z;
    std::cin >> x >> y >> z;
    Tracker a(x), b(y), c(z);
    std::vector<Tracker> v;
    v.reserve(10);
    v.push_back(a);
    v.push_back(b);
    v.push_back(c);
    std::cout << Tracker::copies << " copies, " << Tracker::moves << " moves\n";
    for (const auto &t : v) std::cout << t.name << " ";
    std::cout << "\n";
    return 0;
}
```

```cpp solution
#include <iostream>
#include <string>
#include <utility>
#include <vector>

struct Tracker {
    static int copies, moves;
    std::string name;
    explicit Tracker(std::string n) : name(std::move(n)) {}
    Tracker(const Tracker &o) : name(o.name) { ++copies; }
    Tracker(Tracker &&o) noexcept : name(std::move(o.name)) { ++moves; }
};
int Tracker::copies = 0, Tracker::moves = 0;

int main() {
    std::string x, y, z;
    std::cin >> x >> y >> z;
    Tracker a(x), b(y), c(z);
    std::vector<Tracker> v;
    v.reserve(10);
    v.push_back(a);
    v.push_back(std::move(b));
    v.push_back(std::move(c));
    std::cout << Tracker::copies << " copies, " << Tracker::moves << " moves\n";
    for (const auto &t : v) std::cout << t.name << " ";
    std::cout << "\n";
    return 0;
}
```

```tests
{"name": "one copy, two moves", "stdin": "alpha beta gamma\n", "expected": "1 copies, 2 moves\nalpha beta gamma"}
{"name": "other names", "stdin": "x y z\n", "expected": "1 copies, 2 moves\nx y z", "hidden": true}
```
