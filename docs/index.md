下面给你一个**在本地 Mac（通过 OrbStack 搭建 Kubernetes 环境）**可以运行的“小型工程化”示例，展示如何利用 NGINX Ingress Controller 做灰度发布（Canary Release）。示例包含：

1. **两个 Python Flask 应用（v1 与 v2）**，分别打包到 Docker 镜像中。  
2. **K8s 部署 & Service** 用于运行这两个版本的服务。  
3. **Nginx Ingress + Canary Ingress**，让你可以把 20% 流量切给新版本。  
4. **测试方法**，验证灰度发布是否生效。

> **说明**：  
> - 你在 macOS 上使用 [OrbStack](https://orbstack.dev/) 来跑本地的容器和 Kubernetes 集群（OrbStack 自带 k3s 或 Docker / containerd 的支持），原理上跟在 Docker Desktop 或者 kind 上做类似。只要保证你有可用的 Kubernetes 集群和可用的 Ingress Controller 即可。  
> - 如果尚未安装 [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/), 请先在你的 K8s 集群里安装好。OrbStack 可能自带某些组件，但若不含 Ingress，需要手动安装。  
> - 如果你只想做最简单实验，也可以 `kubectl port-forward` 到 Service 来测试，不使用 Ingress。但这样无法演示“canary”流量分配。本示例主要体现 Canary Ingress 机制。

下面分步骤演示。

---

# 目录结构

可以创建一个文件夹 `flask-canary-demo`（或任意名称），内部结构如下：

```
flask-canary-demo
├── app_v1
│   ├── app.py
│   └── Dockerfile
├── app_v2
│   ├── app.py
│   └── Dockerfile
└── k8s
    ├── deployment_v1.yaml
    ├── deployment_v2.yaml
    ├── service_v1.yaml
    ├── service_v2.yaml
    └── ingress.yaml
```

接下来详细列出各文件内容。

---

# 1. Flask 应用与 Docker 打包

### 1.1 `app_v1/app.py`
```python
from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello_v1():
    return "Hello from Flask v1!\n"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```
- 非常简单的 Flask 应用，返回一行字符串，显示这是 “v1”。

### 1.2 `app_v1/Dockerfile`
```dockerfile
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
```

### 1.3 `app_v2/app.py`
```python
from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello_v2():
    return "Hello from Flask v2 - Canary!\n"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```
- 这里同样的代码结构，但返回字符串显式告诉大家 “v2 - Canary”。

### 1.4 `app_v2/Dockerfile`
```dockerfile
FROM python:3.9-slim
WORKDIR /app
RUN pip install flask
COPY app.py /app/
CMD ["python", "app.py"]
```

---

# 2. 构建并推送镜像

在 Mac 上，你可以使用 OrbStack 集成的 Docker 环境（或者你自己安装的 Docker CLI）来构建镜像。示例命令如下（在项目根目录）：

```bash
# 进入 app_v1 目录
cd app_v1
docker build -t flask-canary-demo:v1 .
# 进入 app_v2 目录
cd ../app_v2
docker build -t flask-canary-demo:v2 .
cd ..
```

上述命令会在本地生成两个镜像：  
- `flask-canary-demo:v1`  
- `flask-canary-demo:v2`

> **提示**：  
> - 如果你本地 Kubernetes 能直接访问本地 Docker 镜像（通常 OrbStack / Docker Desktop 会让 k8s 共用本机镜像），则无需再 push 到远端仓库。  
> - 如果你的 k8s 集群与 Docker 环境隔离，需要你把镜像推到私有镜像仓库，或者配置 `kind load docker-image` / `k3s ctr images import` 等操作，把本地镜像导入集群。  
> - 下面假设你可以直接使用本地镜像（最常见于 Docker Desktop / OrbStack 的集成场景）。

---

# 3. Kubernetes 配置文件

请将以下 YAML 文件放置到 `k8s` 子目录下（名称随意，但注意区分），方便集中管理。

## 3.1 `deployment_v1.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flask-v1
  labels:
    app: flask-canary
    version: v1
spec:
  replicas: 2
  selector:
    matchLabels:
      app: flask-canary
      version: v1
  template:
    metadata:
      labels:
        app: flask-canary
        version: v1
    spec:
      containers:
      - name: flask-app
        image: flask-canary-demo:v1
        ports:
        - containerPort: 5000
```
- 部署 “v1” 版本，副本数 2 个。

## 3.2 `service_v1.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: flask-v1-svc
spec:
  selector:
    app: flask-canary
    version: v1
  ports:
  - port: 80
    targetPort: 5000
```
- Service 名为 `flask-v1-svc`，让外部访问走 80 端口，对应容器内 5000。

## 3.3 `deployment_v2.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flask-v2
  labels:
    app: flask-canary
    version: v2
spec:
  replicas: 1
  selector:
    matchLabels:
      app: flask-canary
      version: v2
  template:
    metadata:
      labels:
        app: flask-canary
        version: v2
    spec:
      containers:
      - name: flask-app
        image: flask-canary-demo:v2
        ports:
        - containerPort: 5000
```
- “v2” 版本，只跑 1 个副本。

## 3.4 `service_v2.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: flask-v2-svc
spec:
  selector:
    app: flask-canary
    version: v2
  ports:
  - port: 80
    targetPort: 5000
```
- Service 名为 `flask-v2-svc`。

## 3.5 `ingress.yaml`

这个文件包含**两个 Ingress**，一个主 Ingress、一个 Canary Ingress，用 NGINX Ingress 的 `canary` 注解实现 80%:20% 流量切分。

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: flask-main-ingress
  annotations:
    kubernetes.io/ingress.class: "nginx"
spec:
  rules:
    - host: flask-demo.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: flask-v1-svc
                port:
                  number: 80
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: flask-canary-ingress
  annotations:
    kubernetes.io/ingress.class: "nginx"

    # Canary 关键注解
    nginx.ingress.kubernetes.io/canary: "true"
    # 这里设定 canary-weight=20，即 ~20% 流量导向 v2
    nginx.ingress.kubernetes.io/canary-weight: "20"
spec:
  rules:
    - host: flask-demo.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: flask-v2-svc
                port:
                  number: 80
```

- 第一个 Ingress（`flask-main-ingress`）匹配 Host `flask-demo.local` 的 `/` 路径，默认转发到 `flask-v1-svc`。  
- 第二个 Ingress（`flask-canary-ingress`）启用 `nginx.ingress.kubernetes.io/canary: "true"`，指定了 `canary-weight: "20"` 表示**约 20%** 流量分给它指向的 `flask-v2-svc`。  

**注意**：这个域名 `flask-demo.local` 是随意取的，你可以用 `/etc/hosts` 来解析到 Ingress Controller 的 IP。

---

# 4. 部署到 Kubernetes

在 `flask-canary-demo/k8s` 目录，执行：
```bash
kubectl apply -f deployment_v1.yaml
kubectl apply -f service_v1.yaml

kubectl apply -f deployment_v2.yaml
kubectl apply -f service_v2.yaml

kubectl apply -f ingress.yaml
```

或者你也可以 `kubectl apply -f .` 一次性应用同目录下全部文件。

**验证**：

```bash
kubectl get deployments
kubectl get svc
kubectl get ingress
```

确保它们都成功创建，并且 Pod 状态正常运行（`kubectl get pods`）。

---

# 5. 配置本地 DNS 解析

如果你想用域名 `flask-demo.local` 访问，需要把它解析到 NGINX Ingress Controller 对外暴露的地址。

1. **查看 Ingress Controller 的服务地址**：  
   ```bash
   kubectl get svc -n ingress-nginx
   ```
   - 可能是 `LoadBalancer` 类型（如果 OrbStack/MetalLB 提供负载均衡 IP）  
   - 或者是 `NodePort` 并且你知道 Node IP。  

2. **编辑 `/etc/hosts`** (在 macOS 上)，例如：
   ```plaintext
   127.0.0.1     flask-demo.local
   ```
   如果 Ingress Controller 暴露在本地 127.0.0.1:80/443。
   或者把 Ingress Controller IP 替换为 `192.168.x.x`，只要能访问即可。

有时 OrbStack 也会给你一个 local domain / IP，视情况而定。只要能让 `curl http://flask-demo.local/` 命中 Ingress 即可。

---

# 6. 测试灰度生效

当你的域名解析完毕后，可以试着请求若干次：

```bash
for i in {1..10}; do curl -s http://flask-demo.local/; done
```

你会看到多数请求返回：
```
Hello from Flask v1!
```
而少数请求返回：
```
Hello from Flask v2 - Canary!
```
根据 `canary-weight=20`，理论上 ~20% 的请求给了 v2。所以如果你请求十次，预期 2~3 次落在 v2。（并非严格每 5 次中必有 1 次，但长期平均值差不多。）

或者你也可以多次访问：
```bash
watch -n 0.5 'curl -s http://flask-demo.local/'
```
观察输出，大部分是 v1，偶尔出现 v2。这样就可以确认**灰度流量分配**在起作用了。

---

# 7. 调整与回滚

1. **提高流量**：  
   如果 v2 版本稳定，你可以 `kubectl edit ingress flask-canary-ingress` 把 `nginx.ingress.kubernetes.io/canary-weight: "20"` 改成更高的数字，如 50、80... 直至 100，把全部流量切到新版本。

2. **停止灰度**：  
   如果发现 v2 出了问题，可以**删除** Canary Ingress 或把 `canary-weight` 改成 0，流量就会回到 v1。这种做法相对简单，算是“手动回滚”流量。

3. **使用其他方式**：  
   - 如果想基于请求头（如某些测试人员 Headers）才命中 v2，可用注解 `nginx.ingress.kubernetes.io/canary-by-header`；  
   - 如果要做更多的自动化金丝雀（如监控指标失败后自动回滚），可考虑 [Flagger](https://github.com/fluxcd/flagger) + NGINX Ingress Controller，自动化执行 canary 加权和回滚流程。  
   - 如果你在集群里安装了 Istio 等 Service Mesh，也可以用更丰富的流量路由。

---

# 总结

通过上述“**Python Flask + Docker + K8s + NGINX Ingress Canary**”的示例工程，你可以在本地（macOS + OrbStack）搭建一个完整的灰度发布流程：

1. **编写两个版本的应用**并打包为镜像。  
2. **在 Kubernetes 部署**各自的 Deployment & Service。  
3. **使用 NGINX Ingress** 定义一个主 Ingress（指向旧版），再定义一个 Canary Ingress（指向新版本并设置 Weight）。  
4. **通过域名**访问并随机抽样验证；发现某个百分比流量命中新版本，以此完成灰度。  
5. 手动调大权重或删除 Canary 配置，就可完成“升级”或“回退”。

这就是最常见的基于 NGINX Ingress 的简单金丝雀实践。若要更“工程化”地自动监控并决定回滚，可以在此基础上集成 CI/CD（Argo CD、Jenkins 等）和 Progressive Delivery 工具（Argo Rollouts、Flagger），让灰度发布更加智能化。  

但对于演示和初步试验，这个 Demo 足以说明**如何工程化地在本地测试灰度/金丝雀**。你只需确认**Ingress Controller**配置正常，**域名解析**正确，就能看到灰度效果。祝实验顺利、玩得愉快!