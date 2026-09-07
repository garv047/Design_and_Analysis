#include <stdio.h>

void merge(int a[], int l, int m, int r)
{
    int temp[r - l + 1];
    int i = l, j = m + 1, k = 0;

    while (i <= m && j <= r)
    {
        if (a[i] <= a[j])
            temp[k++] = a[i++];
        else
            temp[k++] = a[j++];
    }

    while (i <= m)
        temp[k++] = a[i++];

    while (j <= r)
        temp[k++] = a[j++];

    for (i = l, k = 0; i <= r; i++, k++)
        a[i] = temp[k];
}

void mergeSort(int a[], int l, int r)
{
    if (l >= r)
        return;

    int m = (l + r) / 2;

    mergeSort(a, l, m);
    mergeSort(a, m + 1, r);
    merge(a, l, m, r);
}

int main()
{
    int n, q;
    scanf("%d %d", &n, &q);

    int a[n];

    for (int i = 0; i < n; i++)
        scanf("%d", &a[i]);

    mergeSort(a, 0, n - 1);

    while (q--)
    {
        int L, R, count = 0;
        scanf("%d %d", &L, &R);

        for (int i = 0; i < n; i++)
        {
            if (a[i] >= L && a[i] <= R)
                count++;
        }

        printf("%d\n", count);
    }

    return 0;
}
