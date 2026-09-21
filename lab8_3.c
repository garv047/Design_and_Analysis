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
        for (int j = i + 1; j < n; j++)
        {
            if (a[i].start < a[j].start)
            {
                struct Activity temp = a[i];
                a[i] = a[j];
                a[j] = temp;
            }
        }
    }
}

void selectActivities(struct Activity a[], int n, int i)
{
    int j = i + 1;

    while (j < n && a[j].finish > a[i].start)
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

    // Select the activity with latest start time
    printf("(%d, %d) ", a[0].start, a[0].finish);

    selectActivities(a, n, 0);

    return 0;
}
