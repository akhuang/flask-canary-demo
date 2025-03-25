import os
import json
import time
import uuid
import threading
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, abort
import redis

# Initialize Flask application
app = Flask(__name__)

# Configure Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Flash sale configuration
RATE_LIMIT_TOKENS = int(os.getenv("RATE_LIMIT_TOKENS", 100))  # 每个用户初始令牌数
TOKEN_REFILL_RATE = float(os.getenv("TOKEN_REFILL_RATE", 20))  # 每秒补充令牌数
GLOBAL_RATE_LIMIT = int(os.getenv("GLOBAL_RATE_LIMIT", 2000))  # 全局每秒请求限制

# Sample product data (in a real app, this would come from a database)
FLASH_SALE_PRODUCTS = {
    "product1": {
        "id": "product1",
        "name": "Limited Edition Gadget",
        "original_price": 199.99,
        "flash_sale_price": 99.99,
        "quantity": 10,  # 库存数量设为10
        "start_time": int(time.time()),  # Start now for demo purposes
        "end_time": int(time.time()) + 3600,  # End in 1 hour
        "description": "Exclusive high-demand gadget at 50% off!"
    }
}

# 加载 Lua 脚本
def load_lua_script(script_name):
    script_path = os.path.join(os.path.dirname(__file__), 'lua', f'{script_name}.lua')
    with open(script_path, 'r') as f:
        return f.read()

# Initialize product inventory in Redis
def init_product_inventory():
    if redis_client:
        print("Initializing product inventory in Redis...")
        for product_id, product in FLASH_SALE_PRODUCTS.items():
            # Always reset inventory count on startup
            inventory_key = f"flash_sale:inventory:{product_id}"
            redis_client.set(inventory_key, product["quantity"])
            print(f"Set inventory for {product_id} to {product['quantity']}")
            
            # Store product info
            product_key = f"flash_sale:product:{product_id}"
            redis_client.hmset(product_key, {
                "name": product["name"],
                "original_price": product["original_price"],
                "flash_sale_price": product["flash_sale_price"],
                "start_time": product["start_time"],
                "end_time": product["end_time"],
                "description": product["description"]
            })
        print("Product inventory initialization completed")

# Initialize Redis client
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=REDIS_DB,
        decode_responses=True
    )
    redis_client.ping()  # Test connection
    print("Connected to Redis successfully")
    
    # 加载并注册 Lua 脚本
    decrement_inventory_script = load_lua_script('decrement_inventory')
    decrement_inventory_sha = redis_client.script_load(decrement_inventory_script)
    print(f"Loaded Lua script with SHA: {decrement_inventory_sha}")
    
    # Call init_product_inventory after Redis connection is established
    init_product_inventory()
except redis.ConnectionError as e:
    print(f"Failed to connect to Redis: {e}")
    redis_client = None
    decrement_inventory_sha = None

# Initialize order queue processor
def process_order_queue():
    """Background thread to process orders from the queue"""
    if not redis_client:
        return
    
    while True:
        try:
            # Pop an order from the queue
            result = redis_client.blpop("flash_sale:order_queue", timeout=1)
            if result:
                _, order_data = result
                order = json.loads(order_data)
                
                product_id = order["product_id"]
                user_id = order["user_id"]
                
                # Check if product is still available (optimistic locking)
                inventory_key = f"flash_sale:inventory:{product_id}"
                
                # Use a transaction to prevent race conditions
                with redis_client.pipeline() as pipe:
                    while True:
                        try:
                            # Watch for changes in the inventory
                            pipe.watch(inventory_key)
                            
                            # Get current inventory
                            current_inventory = int(pipe.get(inventory_key) or 0)
                            
                            if current_inventory <= 0:
                                # No inventory left
                                pipe.unwatch()
                                # Record failed order
                                redis_client.hmset(f"flash_sale:order:{order['order_id']}", {
                                    "status": "failed",
                                    "reason": "out_of_stock"
                                })
                                break
                            
                            # Start transaction
                            pipe.multi()
                            
                            # Decrement inventory
                            pipe.decr(inventory_key)
                            
                            # Record successful order
                            order_key = f"flash_sale:order:{order['order_id']}"
                            pipe.hmset(order_key, {
                                "status": "success",
                                "product_id": product_id,
                                "user_id": user_id,
                                "price": FLASH_SALE_PRODUCTS[product_id]["flash_sale_price"],
                                "timestamp": int(time.time())
                            })
                            
                            # Execute transaction
                            pipe.execute()
                            break
                            
                        except redis.WatchError:
                            # Optimistic lock failed, retry
                            continue
        except Exception as e:
            print(f"Error processing order queue: {e}")
            time.sleep(1)  # Prevent CPU spinning on errors

# Rate limiting decorator
def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not redis_client:
            return f(*args, **kwargs)
        
        # Get user ID from request (in a real app, this would come from authentication)
        user_id = request.headers.get('X-User-ID', request.remote_addr)
        
        # Check global rate limit first
        global_key = "flash_sale:global_rate_limit"
        current_timestamp = int(time.time())
        previous_timestamp = current_timestamp - 1
        
        # 使用 pipeline 保证原子性
        pipe = redis_client.pipeline()
        # 获取上一秒的计数
        pipe.get(f"{global_key}:{previous_timestamp}")
        # 递增当前秒的计数
        pipe.incr(f"{global_key}:{current_timestamp}")
        # 设置过期时间
        pipe.expire(f"{global_key}:{current_timestamp}", 5)  # 保留5秒以便于监控
        results = pipe.execute()
        
        # 获取前一秒和当前秒的请求总数
        prev_count = int(results[0] or 0)
        current_count = int(results[1] or 0)
        
        # 如果一秒内的总请求数超过限制
        if prev_count + current_count > GLOBAL_RATE_LIMIT:
            return jsonify({"error": "Too many requests overall"}), 429
        
        # Check user-specific rate limit using token bucket algorithm
        user_key = f"flash_sale:rate_limit:{user_id}"
        
        # 使用 pipeline 保证原子性
        pipe = redis_client.pipeline()
        pipe.hmget(user_key, ["tokens", "last_request"])
        pipe.time()
        results = pipe.execute()
        
        tokens, last_request = results[0]
        server_time = float(results[1][0]) + float(results[1][1]) / 1000000  # 转换为带微秒的时间戳
        
        # Initialize if not exists
        if tokens is None:
            tokens = float(RATE_LIMIT_TOKENS)
            last_request = server_time
        else:
            tokens = float(tokens)
            last_request = float(last_request)
            
            # Calculate token refill
            time_passed = server_time - last_request
            token_refill = time_passed * TOKEN_REFILL_RATE
            tokens = min(float(RATE_LIMIT_TOKENS), tokens + token_refill)
        
        # Check if user has enough tokens
        if tokens < 1:
            return jsonify({"error": "Rate limit exceeded"}), 429
        
        # Consume a token and update state atomically
        pipe = redis_client.pipeline()
        tokens -= 1
        pipe.hmset(user_key, {
            "tokens": str(tokens),
            "last_request": str(server_time)
        })
        pipe.expire(user_key, 3600)  # 1 hour
        pipe.execute()
        
        return f(*args, **kwargs)
    
    return decorated_function

# Start background thread for processing orders
order_processor = threading.Thread(target=process_order_queue, daemon=True)
order_processor.start()

@app.route("/")
def hello():
    version = os.getenv("FLASK_VERSION", "unknown")
    return f"Hello from Flask version {version}!\n"

@app.route("/health")
def health_check():
    return "OK", 200

# Flash Sale API endpoints
@app.route("/api/flash-sales", methods=["GET"])
@rate_limit
def list_flash_sales():
    """Get all active flash sale products"""
    if not redis_client:
        return jsonify({"error": "Redis connection not available"}), 503
    
    current_time = int(time.time())
    active_products = []
    
    for product_id, product in FLASH_SALE_PRODUCTS.items():
        if product["start_time"] <= current_time <= product["end_time"]:
            # Get current inventory
            inventory_key = f"flash_sale:inventory:{product_id}"
            remaining = int(redis_client.get(inventory_key) or 0)
            
            # Add product with remaining inventory
            product_data = product.copy()
            product_data["remaining"] = remaining
            active_products.append(product_data)
    
    return jsonify({
        "flash_sales": active_products,
        "count": len(active_products),
        "server_time": current_time
    })

@app.route("/api/flash-sales/<product_id>", methods=["GET"])
@rate_limit
def get_flash_sale(product_id):
    """Get details of a specific flash sale product"""
    if not redis_client:
        return jsonify({"error": "Redis connection not available"}), 503
    
    if product_id not in FLASH_SALE_PRODUCTS:
        return jsonify({"error": "Product not found"}), 404
    
    product = FLASH_SALE_PRODUCTS[product_id]
    current_time = int(time.time())
    
    # Check if the flash sale is active
    if not (product["start_time"] <= current_time <= product["end_time"]):
        status = "upcoming" if current_time < product["start_time"] else "ended"
        return jsonify({
            "product": product,
            "status": status,
            "server_time": current_time
        })
    
    # Get current inventory
    inventory_key = f"flash_sale:inventory:{product_id}"
    remaining = int(redis_client.get(inventory_key) or 0)
    
    product_data = product.copy()
    product_data["remaining"] = remaining
    product_data["status"] = "active"
    
    return jsonify({
        "product": product_data,
        "server_time": current_time
    })

@app.route("/api/flash-sales/<product_id>/order", methods=["POST"])
@rate_limit
def place_order(product_id):
    """Place an order for a flash sale product with strict inventory control"""
    if not redis_client:
        return jsonify({"error": "Redis connection not available"}), 503
    
    if product_id not in FLASH_SALE_PRODUCTS:
        return jsonify({"error": "Product not found"}), 404
    
    product = FLASH_SALE_PRODUCTS[product_id]
    current_time = int(time.time())
    
    # Check if the flash sale is active
    if not (product["start_time"] <= current_time <= product["end_time"]):
        status = "upcoming" if current_time < product["start_time"] else "ended"
        return jsonify({
            "error": f"Flash sale is {status}",
            "status": status
        }), 400
    
    # 使用原子性Lua脚本处理库存和订单
    try:
        # 生成订单ID和获取用户ID
        order_id = str(uuid.uuid4())
        user_id = request.headers.get('X-User-ID', request.remote_addr)
        
        # 设置库存和订单键
        inventory_key = f"flash_sale:inventory:{product_id}"
        order_key = f"flash_sale:order:{order_id}"
        
        # 使用预加载的Lua脚本原子性地检查和减少库存
        result = redis_client.evalsha(
            decrement_inventory_sha,
            2,                           # 两个键名
            inventory_key,               # KEYS[1]: 库存键
            order_key,                   # KEYS[2]: 订单键
            user_id,                     # ARGV[1]: 用户ID
            product_id,                  # ARGV[2]: 产品ID
            product["flash_sale_price"], # ARGV[3]: 价格
            current_time,                # ARGV[4]: 时间戳
            product["quantity"]          # ARGV[5]: 初始库存限制
        )
        
        # 解析Lua脚本返回结果
        success_code = result[0]
        message = result[1]
        
        if success_code == 1:  # 成功
            return jsonify({
                "message": "Order placed successfully",
                "order_id": order_id,
                "status": "success"
            })
        else:  # 失败（如库存不足）
            return jsonify({
                "error": message,
                "status": "failed"
            }), 400
            
    except Exception as e:
        # 记录错误
        print(f"Error processing order: {e}")
        return jsonify({
            "error": "Internal server error",
            "status": "error"
        }), 500

@app.route("/api/orders/<order_id>", methods=["GET"])
@rate_limit
def get_order_status(order_id):
    """Check the status of an order"""
    if not redis_client:
        return jsonify({"error": "Redis connection not available"}), 503
    
    order_key = f"flash_sale:order:{order_id}"
    order_data = redis_client.hgetall(order_key)
    
    if not order_data:
        return jsonify({"error": "Order not found"}), 404
    
    return jsonify({
        "order_id": order_id,
        "status": order_data.get("status", "unknown"),
        "details": order_data
    })

if __name__ == "__main__":
    # Start on 0.0.0.0:5001 to avoid conflict with AirPlay on macOS
    app.run(host="0.0.0.0", port=5001)
