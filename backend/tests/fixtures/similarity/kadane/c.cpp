#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    int n;
    cin >> n;
    vector<long long> a(n);
    for (auto &x : a) cin >> x;
    long long result = a[0], running = a[0];
    for (int i = 1; i < n; ++i) {
        running = max(a[i], running + a[i]);
        result = max(result, running);
    }
    cout << result << "\n";
}
