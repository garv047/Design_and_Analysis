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

    int low = 0;
    int high = n - 1;
    int firstOne = n;

    while (low <= high)
    {
        int mid = (low + high) / 2;

        if (arr[mid] == 1)
        {
            firstOne = mid;
            high = mid - 1;
        }
        else
        {
            low = mid + 1;
        }
    }

    int count0 = firstOne;
    int count1 = n - firstOne;

    if (count0 > count1)
    {
        printf("0\n");
    }
    else if (count1 > count0)
    {
        printf("1\n");
    }
    else
    {
        printf("-1\n");
    }

    return 0;
}