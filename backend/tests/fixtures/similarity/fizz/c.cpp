#include <iostream>
#include <string>
using namespace std;

int main() {
    int n;
    cin >> n;
    for (int x = 1; x <= n; ++x) {
        string s;
        if (x % 3 == 0) s += "Chai";
        if (x % 5 == 0) s += "Samosa";
        cout << (s.empty() ? to_string(x) : s) << '\n';
    }
    return 0;
}
