#include <stdio.h>

int main(void)
{
    int j = 42;
    int *a = &j;
    int k = *a;

    printf("j--->%p\n", (void*)&j);
    printf("a--->%p\n", (void*)a);  // Указатель выводим как %p
    printf("k--->%p\n", (void*)&k);         // Целое число выводим как %d

    return 0;
}
