#include <stdio.h>

struct Item
{
    int value;
    int weight;
    float ratio;
};

int main()
{
    int n, W;
    scanf("%d %d", &n, &W);

    struct Item a[n];

    for (int i = 0; i < n; i++)
    {
        scanf("%d %d", &a[i].value, &a[i].weight);
        a[i].ratio = (float)a[i].value / a[i].weight;
    }

    // Sort by value/weight ratio
    for (int i = 0; i < n - 1; i++)
    {
        for (int j = i + 1; j < n; j++)
        {
            if (a[i].ratio < a[j].ratio)
            {
                struct Item temp = a[i];
                a[i] = a[j];
                a[j] = temp;
            }
        }
    }

    float total = 0;

    for (int i = 0; i < n; i++)
    {
        if (W >= a[i].weight)
        {
            W -= a[i].weight;
            total += a[i].value;
        }
        else
        {
            total += a[i].ratio * W;
            break;
        }
    }

    printf("%.2f", total);

    return 0;
}
