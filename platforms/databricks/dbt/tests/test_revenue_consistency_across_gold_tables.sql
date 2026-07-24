-- Revenue consistency test
-- Ensures that total revenue in gold_product_performance matches
-- the sum of revenue in gold_daily_revenue (allowing for rounding differences)

with daily_totals as (
  select
    product,
    sum(total_revenue) as daily_total_revenue
  from {{ source('gold', 'gold_daily_revenue') }}
  group by product
),

product_totals as (
  select
    product,
    total_revenue as product_total_revenue
  from {{ source('gold', 'gold_product_performance') }}
)

select
  coalesce(d.product, p.product) as product,
  d.daily_total_revenue,
  p.product_total_revenue,
  abs(coalesce(d.daily_total_revenue, 0) - coalesce(p.product_total_revenue, 0)) as revenue_diff
from daily_totals d
full outer join product_totals p on d.product = p.product
where abs(coalesce(d.daily_total_revenue, 0) - coalesce(p.product_total_revenue, 0)) > 0.01
