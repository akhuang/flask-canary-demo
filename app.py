import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    version = os.getenv("FLASK_VERSION", "unknown")
    return f"Hello from Flask version {version}!\n"

if __name__ == "__main__":
    # 启动在 0.0.0.0:5000
    app.run(host="0.0.0.0", port=5000)
