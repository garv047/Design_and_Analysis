#include <stdio.h>

long long merge(int a[], int l, int m, int r)
{
    int i = l, j = m + 1, k = 0;
    int temp[r - l + 1];
    long long inv = 0;

    while (i <= m && j <= r)
    {
        if (a[i] <= a[j])
            temp[k++] = a[i++];
        else
        {
            temp[k++] = a[j++];
            inv += m - i + 1;
        }
    }

    while (i <= m)
        temp[k++] = a[i++];

    while (j <= r)
        temp[k++] = a[j++];

    for (i = l, k = 0; i <= r; i++, k++)
        a[i] = temp[k];

    return inv;
}

long long sort(int a[], int l, int r)
{
    if (l >= r)
        return 0;

    int m = (l + r) / 2;

    long long inv = 0;

    inv += sort(a, l, m);
    inv += sort(a, m + 1, r);
    inv += merge(a, l, m, r);

    return inv;
}

int main()
{
    int n;
    scanf("%d", &n);

    int a[n];

    for (int i = 0; i < n; i++)
        scanf("%d", &a[i]);

    printf("%lld", sort(a, 0, n - 1));

    return 0;
}
