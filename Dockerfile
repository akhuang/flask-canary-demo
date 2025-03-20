FROM python:3.9-slim
WORKDIR /app
RUN pip install flask
COPY app.py /app/
# Flask 将读取 FLASK_VERSION 环境变量来显示版本

# 缺省指定 version=unknown
ENV FLASK_VERSION=unknown
CMD ["python", "app.py"]
