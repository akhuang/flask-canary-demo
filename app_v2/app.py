from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello_v2():
    return "Hello from Flask v2 - Canary!\n"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)