#include <stdio.h>

int main() {
    int limit;
    scanf("%d", &limit);
    int k = 1;
    while (k <= limit) {
        int printed = 0;
        if (k % 3 == 0) { printf("Chai"); printed = 1; }
        if (k % 5 == 0) { printf("Samosa"); printed = 1; }
        if (!printed) printf("%d", k);
        printf("\n");
        k++;
    }
}
