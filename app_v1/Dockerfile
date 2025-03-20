# 使用 python:3.9-slim 作为基础镜像
FROM python:3.9-slim

# 在容器里创建目录
WORKDIR /app

# 安装 flask
RUN pip install flask

# 复制当前目录的代码到容器
COPY app.py /app/

# 启动 Flask
CMD ["python", "app.py"]
