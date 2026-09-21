#include <stdio.h>
#include <stdlib.h>

int compare(const void *a, const void *b)
{
    int *x = (int *)a;
    int *y = (int *)b;

    return x[1] - y[1];
}

int main()
{
    int n;
    scanf("%d", &n);

    int points[n][2];

    for (int i = 0; i < n; i++)
        scanf("%d %d", &points[i][0], &points[i][1]);

    // Sort by ending point
    qsort(points, n, sizeof(points[0]), compare);

    int arrows = 1;
    int arrow = points[0][1];

    for (int i = 1; i < n; i++)
    {
        if (points[i][0] > arrow)
        {
            arrows++;
            arrow = points[i][1];
        }
    }

    printf("%d", arrows);

    return 0;
}
