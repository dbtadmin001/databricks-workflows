-- Spend tier consistency test
-- Ensures spend_tier classifications match the business rules

select
  customerID,
  customer_name,
  total_spend,
  spend_tier
from {{ source('gold', 'gold_customer_segments') }}
where (spend_tier = 'High' and total_spend < 500)
   or (spend_tier = 'Medium' and (total_spend < 200 or total_spend >= 500))
   or (spend_tier = 'Low' and total_spend >= 200)
