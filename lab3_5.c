#include <stdio.h>

int main()
{
    int n;
    scanf("%d", &n);

    int arr[n];

    for (int i = 0; i < n; i++)
    {
        scanf("%d", &arr[i]);
    }

    int count0 = 0;
    int count1 = 0;

    for (int i = 0; i < n; i++)
    {
        if (arr[i] == 0)
            count0++;
        else
            count1++;
    }

    if (count0 > count1)
        printf("0");
    else if (count1 > count0)
        printf("1");
    else
        printf("-1");

    return 0;
}