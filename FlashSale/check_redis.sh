#!/bin/bash
# 检查Redis中的关键信息

echo "===== Redis 库存和订单计数调试 ====="
echo "库存状态:"
docker exec -it flask-canary-demo-redis-1 redis-cli get "flash_sale:inventory:product1"
echo "订单计数:"
docker exec -it flask-canary-demo-redis-1 redis-cli get "flash_sale:order_count:product1"
echo "========================="