#include <stdio.h>

void quicksort(int a[], int low, int high)
{
    if (low < high)
    {
        int pivot = a[high];
        int i = low - 1;
        int j, temp;

        for (j = low; j < high; j++)
        {
            if (a[j] <= pivot)
            {
                i++;
                temp = a[i];
                a[i] = a[j];
                a[j] = temp;
            }
        }

        temp = a[i + 1];
        a[i + 1] = a[high];
        a[high] = temp;

        int p = i + 1;

        quicksort(a, low, p - 1);
        quicksort(a, p + 1, high);
    }
}

int main()
{
    int n, i;

    scanf("%d", &n);

    int a[n];

    for (i = 0; i < n; i++)
        scanf("%d", &a[i]);

    quicksort(a, 0, n - 1);

    for (i = 0; i < n; i++)
        printf("%d ", a[i]);

    return 0;
}