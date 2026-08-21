#include <stdio.h>

int main()
{
    int n, K;
    int found = 0;

    scanf("%d", &n);

    int arr[n];

    for (int i = 0; i < n; i++)
    {
        scanf("%d", &arr[i]);
    }

    scanf("%d", &K);

    for (int i = 0; i < n - 1; i++)
    {
        int target = K - arr[i];

        int low = i + 1;
        int high = n - 1;

        while (low <= high)
        {
            int mid = (low + high) / 2;

            if (arr[mid] == target)
            {
                printf("%d %d\n", arr[i], arr[mid]);
                found = 1;
                break;
            }
            else if (arr[mid] < target)
            {
                low = mid + 1;
            }
            else
            {
                high = mid - 1;
            }
        }
    }

    if (found == 0)
    {
        printf("-1\n");
    }

    return 0;
}