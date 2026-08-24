#include <stdio.h>
#include <stdlib.h>

void quicksort(int a[], int low, int high)
{
    if (low < high)
    {
        int r = low + rand() % (high - low + 1);

        int temp = a[r];
        a[r] = a[high];
        a[high] = temp;

        int pivot = a[high];
        int i = low - 1;

        for (int j = low; j < high; j++)
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

        quicksort(a, low, i);
        quicksort(a, i + 2, high);
    }
}

int main()
{
    int n;
    scanf("%d", &n);

    int a[n];

    for (int i = 0; i < n; i++)
        scanf("%d", &a[i]);

    quicksort(a, 0, n - 1);

    for (int i = 0; i < n; i++)
        printf("%d ", a[i]);

    return 0;
}