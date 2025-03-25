-- Initialize the request counter
counter = 0
threads = {}

function setup(thread)
  thread:set("id", counter)
  table.insert(threads, thread)
  counter = counter + 1
end

function init(args)
  -- Generate a random User ID for this thread
  math.randomseed(os.time() + id * 1000)
  user_id = math.random(1, 10000)
  request_count = 0
  -- Create a fixed user ID for this thread
  thread_user_id = "user-" .. user_id
end

function request()
  request_count = request_count + 1
  -- Set a custom user ID header to simulate different users
  headers = {}
  headers["Content-Type"] = "application/json"
  -- Use the fixed thread_user_id instead of generating a new one per request
  headers["X-User-ID"] = thread_user_id
  
  -- This is a POST request with an empty body
  return wrk.format("POST", nil, headers, "")
end

function response(status, headers, body)
  if status == 200 then
    -- Successfully submitted an order
    local order_response = body
    local success_count = wrk.thread:get("success_count") or 0
    wrk.thread:set("success_count", success_count + 1)
  elseif status == 429 then
    -- Rate limited
    local rate_limited_count = wrk.thread:get("rate_limited_count") or 0
    wrk.thread:set("rate_limited_count", rate_limited_count + 1)
  elseif status == 400 then
    -- Product sold out or other client error
    local sold_out_count = wrk.thread:get("sold_out_count") or 0
    wrk.thread:set("sold_out_count", sold_out_count + 1)
  else
    -- Other errors
    local error_count = wrk.thread:get("error_count") or 0
    wrk.thread:set("error_count", error_count + 1)
  end
end

function done(summary, latency, requests)
  io.write("\n----- Flash Sale Order Test Results -----\n")
  
  for index, thread in ipairs(threads) do
    local success = thread:get("success_count") or 0
    local rate_limited = thread:get("rate_limited_count") or 0
    local sold_out = thread:get("sold_out_count") or 0
    local errors = thread:get("error_count") or 0
    
    io.write(string.format("Thread %d: Success=%d, Rate Limited=%d, Sold Out=%d, Errors=%d\n", 
                         index, success, rate_limited, sold_out, errors))
  end
  
  io.write("\nTotal requests: " .. summary.requests .. "\n")
  io.write("Total errors: " .. summary.errors.status .. "\n")
  io.write("Mean latency: " .. string.format("%.2f", latency.mean / 1000) .. " ms\n")
  io.write("Max latency: " .. string.format("%.2f", latency.max / 1000) .. " ms\n")
  io.write("Requests/sec: " .. string.format("%.2f", summary.requests / summary.duration * 1000000) .. "\n")
end