#include <stdio.h>
#include <stdbool.h>

int main(void) {
    int n;
    scanf("%d", &n);
    static bool composite[1000001];
    int count = 0;
    for (int i = 2; i <= n; i++) {
        if (!composite[i]) {
            count++;
            for (long long j = (long long)i * i; j <= n; j += i)
                composite[j] = true;
        }
    }
    printf("%d\n", count);
    return 0;
}
