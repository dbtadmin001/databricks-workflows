-- No negative revenue test
-- Ensures all revenue-related columns are non-negative across Gold tables

select 'gold_daily_revenue' as table_name, transaction_date as record_id, total_revenue as amount
from {{ source('gold', 'gold_daily_revenue') }}
where total_revenue < 0

union all

select 'gold_product_performance' as table_name, product as record_id, total_revenue as amount
from {{ source('gold', 'gold_product_performance') }}
where total_revenue < 0

union all

select 'gold_franchise_ranking' as table_name, franchiseID as record_id, total_revenue as amount
from {{ source('gold', 'gold_franchise_ranking') }}
where total_revenue < 0

union all

select 'gold_customer_segments' as table_name, customerID as record_id, total_spend as amount
from {{ source('gold', 'gold_customer_segments') }}
where total_spend < 0
