#include <bits/stdc++.h>
using namespace std;

int main() {
    int n, q;
    cin >> n >> q;
    vector<int> v(n);
    for (int &e : v) cin >> e;
    string out;
    while (q-- > 0) {
        int target;
        cin >> target;
        auto it = lower_bound(v.begin(), v.end(), target);
        if (it == v.end() || *it != target) out += "-1\n";
        else out += to_string(it - v.begin() + 1) + "\n";
    }
    cout << out;
}
