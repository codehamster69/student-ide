#include <iostream>
#include <vector>
using namespace std;

int main() {
    int n;
    cin >> n;
    vector<char> sieve(n + 1, 1);
    sieve[0] = 0;
    if (n >= 1) sieve[1] = 0;
    int answer = 0;
    for (int p = 2; p <= n; ++p) {
        if (!sieve[p]) continue;
        ++answer;
        for (int m = 2 * p; m <= n; m += p) sieve[m] = 0;
    }
    cout << answer << endl;
    return 0;
}
