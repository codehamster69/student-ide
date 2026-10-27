#include <stdio.h>

int is_prime(int x) {
    if (x < 2) return 0;
    if (x % 2 == 0) return x == 2;
    for (int d = 3; d * d <= x; d += 2) {
        if (x % d == 0) return 0;
    }
    return 1;
}

int main() {
    int limit, total = 0;
    if (scanf("%d", &limit) != 1) return 1;
    for (int k = 1; k <= limit; ++k)
        total += is_prime(k);
    printf("%d\n", total);
}
