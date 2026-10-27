#include <stdio.h>
#include <string.h>

int main(void) {
    char line[10005];
    char *words[5005];
    int count = 0;
    if (!fgets(line, sizeof(line), stdin)) return 0;
    char *tok = strtok(line, " \n");
    while (tok != NULL) {
        words[count++] = tok;
        tok = strtok(NULL, " \n");
    }
    for (int i = count - 1; i >= 0; i--) {
        printf("%s", words[i]);
        if (i > 0) printf(" ");
    }
    printf("\n");
    return 0;
}
