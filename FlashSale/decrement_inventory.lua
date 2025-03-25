-- 采用单一键的严格库存控制脚本
-- KEYS[1]: 库存键名
-- KEYS[2]: 订单键名 
-- ARGV[1]: 用户ID
-- ARGV[2]: 产品ID
-- ARGV[3]: 价格
-- ARGV[4]: 时间戳
-- ARGV[5]: 初始库存限制

-- 获取当前库存
local currentInventory = tonumber(redis.call('get', KEYS[1]) or "0")
local maxInventory = tonumber(ARGV[5])

-- 添加调试日志
redis.call('rpush', 'debug:inventory_log', 'Checking inventory: ' .. currentInventory)

-- 检查库存是否充足
if currentInventory <= 0 then
    return {0, "out_of_stock"}  -- 库存不足
end

-- 严格控制库存范围
if currentInventory > maxInventory then
    redis.call('set', KEYS[1], maxInventory)
    currentInventory = maxInventory
    redis.call('rpush', 'debug:inventory_log', 'Reset inventory to: ' .. currentInventory)
end

-- 减少库存并记录操作
redis.call('decr', KEYS[1])
redis.call('rpush', 'debug:inventory_log', 'Decreased inventory to: ' .. (currentInventory - 1))

-- 记录订单信息
redis.call('hmset', KEYS[2],
    "status", "success",
    "product_id", ARGV[2],
    "user_id", ARGV[1],
    "price", ARGV[3],
    "timestamp", ARGV[4],
    "inventory_at_order", currentInventory
)

-- 返回成功
return {1, "success", currentInventory}  -- 下单成功，返回下单时的库存