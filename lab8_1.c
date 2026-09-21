#include <stdio.h>

struct Activity
{
    int start;
    int finish;
};

void sort(struct Activity a[], int n)
{
    for (int i = 0; i < n - 1; i++)
    {
        for (int j = 0; j < n - i - 1; j++)
        {
            if (a[j].finish > a[j + 1].finish)
            {
                struct Activity temp = a[j];
                a[j] = a[j + 1];
                a[j + 1] = temp;
            }
        }
    }
}

void selectActivities(struct Activity a[], int n, int i)
{
    int j = i + 1;

    while (j < n && a[j].start < a[i].finish)
        j++;

    if (j < n)
    {
        printf("(%d, %d) ", a[j].start, a[j].finish);
        selectActivities(a, n, j);
    }
}

int main()
{
    int n;
    scanf("%d", &n);

    struct Activity a[n];

    for (int i = 0; i < n; i++)
        scanf("%d %d", &a[i].start, &a[i].finish);

    sort(a, n);

    // First activity is always selected
    printf("(%d, %d) ", a[0].start, a[0].finish);

    selectActivities(a, n, 0);

    return 0;
}
