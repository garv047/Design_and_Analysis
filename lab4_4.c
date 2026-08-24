#include <stdio.h>

void swap(char *a, char *b)
{
    char t = *a;
    *a = *b;
    *b = t;
}

void match(char nuts[], char bolts[], int n)
{
    for (int i = 0; i < n; i++)
    {
        for (int j = i; j < n; j++)
        {
            if (nuts[i] == bolts[j])
            {
                swap(&bolts[i], &bolts[j]);
                break;
            }
        }
    }
}

int main()
{
    int n;
    scanf("%d", &n);

    char nuts[n], bolts[n];

    for (int i = 0; i < n; i++)
        scanf(" %c", &nuts[i]);

    for (int i = 0; i < n; i++)
        scanf(" %c", &bolts[i]);

    match(nuts, bolts, n);

    for (int i = 0; i < n; i++)
        printf("%c ", nuts[i]);

    printf("\n");

    for (int i = 0; i < n; i++)
        printf("%c ", bolts[i]);

    return 0;
}