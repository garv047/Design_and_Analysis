#include <stdio.h>

int sum(int arr[], int n, int divisor)
{
    int total = 0;

    for (int i = 0; i < n; i++)
    {
        total = total + (arr[i] + divisor - 1) / divisor;
    }

    return total;
}

int binarySearch(int arr[], int n, int threshold, int low, int high)
{
    if (low == high)
        return low;

    int mid = (low + high) / 2;

    if (sum(arr, n, mid) <= threshold)
    {
        return binarySearch(arr, n, threshold, low, mid);
    }
    else
    {
        return binarySearch(arr, n, threshold, mid + 1, high);
    }
}

int main()
{
    int n, threshold;

    scanf("%d", &n);

    int nums[n];

    for (int i = 0; i < n; i++)
    {
        scanf("%d", &nums[i]);
    }

    scanf("%d", &threshold);

    int max = nums[0];

    for (int i = 1; i < n; i++)
    {
        if (nums[i] > max)
            max = nums[i];
    }

    int answer = binarySearch(nums, n, threshold, 1, max);

    printf("%d\n", answer);

    return 0;
}