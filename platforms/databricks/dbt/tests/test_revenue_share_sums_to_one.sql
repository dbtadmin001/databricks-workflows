-- Revenue share sum test
-- Ensures that revenue_share across all products sums to approximately 1.0

with revenue_share_sum as (
  select sum(revenue_share) as total_share
  from {{ source('gold', 'gold_product_performance') }}
)

select total_share
from revenue_share_sum
where abs(total_share - 1.0) > 0.0001
