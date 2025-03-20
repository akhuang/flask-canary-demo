下文将给出一个从零开始、完全使用 Argo CD（结合 Argo Rollouts）来做GitOps 金丝雀发布的具体步骤示例，基于前面提到的“只有一套代码（Flask App）”的工程思路，但这次不使用命令行去 kubectl apply 或 kubectl set image。所有部署都由 Argo CD 检测 Git 仓库的变化后自动应用到集群。这样你在生产环境就无需命令行，所有变更都通过Git 提交可审计、可回滚。

⸻

场景假设
	1.	开发机：macOS + OrbStack（一个单节点 k3s/k8s）。
	2.	Flask App：只有一套 app.py 和 Dockerfile，通过不同 Build Arg/Tag 生成 v1、v2 镜像。
	3.	GitHub 仓库（或其他 Git）有两个仓库：
	•	代码仓库（Code Repo）：存放 app.py, Dockerfile。
	•	配置仓库（Config Repo）：存放 Kubernetes 配置，包括 Rollout.yaml, Service.yaml, Ingress.yaml。Argo CD 只会 watch 这个仓库。
	4.	Argo Rollouts：我们已在集群中安装（若没装，下面也包含安装步骤）。
	5.	Argo CD：我们会安装后，在浏览器中配置它指向 Config Repo。只要你在 Config Repo 中更新镜像 tag 或金丝雀策略，Argo CD 就会自动把新配置同步到集群，触发金丝雀发布。

⸻

0. 环境准备

如果你已经有一个OrbStack Kubernetes集群，且安装了NGINX Ingress、Argo Rollouts，可以略过对应环节；否则按顺序安装：
	1.	OrbStack + k8s
	•	安装 OrbStack 并启用 Docker/Kubernetes。
	•	验证 kubectl get nodes 能看到一个 orbstack 节点 Ready。
	2.	安装/启用 NGINX Ingress

kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml

等待 ingress-nginx-controller Pod Running。

	3.	安装 Argo Rollouts

kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f \
  https://raw.githubusercontent.com/argoproj/argo-rollouts/stable/manifests/install.yaml

	•	验证 kubectl get pods -n argo-rollouts 正常。

⸻

1. 安装 Argo CD

1.1 安装 Argo CD 核心

kubectl create namespace argocd

# 安装最新 stable 版 Argo CD
kubectl apply -n argocd -f \
  https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

	•	等待一会儿，kubectl get pods -n argocd 显示 argocd-server, argocd-repo-server 等组件全部 Running。

1.2 配置访问 Argo CD Web UI

Argo CD 提供一个 argocd-server Service。你可以端口转发或Ingress暴露：
	1.	端口转发（最简单）：

kubectl port-forward svc/argocd-server -n argocd 8080:443

然后访问 https://localhost:8080 查看 Argo CD UI（浏览器可能提示不安全证书，忽略即可）。

	2.	(可选) Ingress：也可以为 argocd-server 建一个 Ingress 记录 <something>.docker 之类的域名。视情况而定，这里用端口转发最简单。

1.3 获取初始登录密码

Argo CD 默认 admin 密码是 argocd-server Pod 所在 namespace 里 argocd-initial-admin-secret:

kubectl get secret argocd-initial-admin-secret -n argocd \
 -o jsonpath="{.data.password}" | base64 -d

复制此密码，在浏览器端登录 admin 用户。

⸻

2. 准备两个 Git 仓库

GitOps 通常将业务代码和集群配置分离，这里示例为Config Repo放在 GitHub / GitLab / Gitea / 本地 Git 均可。
	1.	代码仓库 (例如 my-flask-app)
	•	只有 app.py, Dockerfile。
	•	CI/CD 或手动 build 出 myflask:v1、myflask:v2 并推到镜像仓库。
	•	不详细展开，因为重点是 Argo CD + 配置仓库。
	2.	配置仓库 (例如 my-flask-app-config)
	•	里面有 rollout.yaml, services.yaml, ingress.yaml 等 K8s 资源声明。
	•	每当你编辑这些 YAML 并 push 到该仓库，Argo CD 侦测到后自动同步到 K8s。

示例结构：

my-flask-app-config
 ├── rollout.yaml
 ├── service.yaml
 └── ingress.yaml

(你也可以合并进一个 all.yaml，随意)

⸻

3. 编写 YAML：Rollout + Service + Ingress

与之前类似，但把 image 改为一个占位值(比如 myflask:v1)。以下示例贴出三个文件放在 my-flask-app-config/ 里。

3.1 rollout.yaml

apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: flask-rollout
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-flask-app
  template:
    metadata:
      labels:
        app: my-flask-app
    spec:
      containers:
      - name: flask-app
        image: myflask:v1   # <--- 改成你推到仓库的镜像repo:tag
        ports:
        - containerPort: 5000

  strategy:
    canary:
      stableService: flask-stable-svc
      canaryService: flask-canary-svc
      steps:
      - setWeight: 20
      - pause: { duration: 30 }
      - setWeight: 100

解释：
	•	初始 image: myflask:v1 表示 stable 版。
	•	之后若你将此值改为 myflask:v2 并 push 到 git，Argo CD 将自动发现，触发金丝雀。

3.2 service.yaml

apiVersion: v1
kind: Service
metadata:
  name: flask-stable-svc
spec:
  selector:
    app: my-flask-app
  ports:
  - port: 80
    targetPort: 5000

---
apiVersion: v1
kind: Service
metadata:
  name: flask-canary-svc
spec:
  selector:
    app: my-flask-app
  ports:
  - port: 80
    targetPort: 5000

3.3 ingress.yaml

apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: flask-ingress
  namespace: default
  annotations:
    kubernetes.io/ingress.class: "nginx"
    # 如果你希望 Rollouts自己管理某些 annotation，可以加:
    # argo-rollouts.argoproj.io/managed-by: "flask-rollout"
spec:
  rules:
  - host: flask-gitops.docker
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: flask-stable-svc
            port:
              number: 80

	•	host: flask-gitops.docker 假设 OrbStack .docker 域名可自动解析。若不行，可改 demo.k8s.orb.local 或自己 /etc/hosts。
	•	stable svc 作为默认后端, Argo Rollouts 在金丝雀期间会注入 canary-svc 20% 流量。

将这三个文件推到你配置仓库 my-flask-app-config/ 并 git commit && git push。

⸻

4. 在 Argo CD 创建 Application

接下来，让 Argo CD 知道 “这个仓库中 default 分支下的 YAML 要部署到集群某命名空间”。可以用 Argo CD UI 或 CLI。这里演示UI方式：
	1.	浏览器访问 Argo CD (https://localhost:8080 端口转发假设).
	2.	登录：用户名 admin，密码见第1.3步。
	3.	New Application：
	•	Application Name：flask-gitops (随意)
	•	Project：default (内置)
	•	Sync Policy：选择手动或自动。示例我们选“自动”（Auto-Sync）可自动更新。
	•	Repository URL：填你 my-flask-app-config repo 地址（Git HTTPS/SSH），例如 https://github.com/YourOrg/my-flask-app-config.git
	•	Revision：main 或 master (你默认分支)
	•	Path：/ (如果 YAML 在仓库根目录)
	•	Cluster：默认 local cluster(https://kubernetes.default.svc)
	•	Namespace：default
	•	其他保持默认即可。然后点击 “Create”。
	4.	Argo CD 会立即检出仓库里的 YAML 并应用到集群。此时 kubectl get rollout, kubectl get svc, kubectl get ingress 都可看到资源已创建。

⸻

5. 验证初始部署

Argo CD 界面里 Applications -> flask-gitops 看到 Status=Healthy, Sync=Synced。
	•	Rollout 会创建3个 Pod，运行 myflask:v1。
	•	访问 http://flask-gitops.docker/ (若 OrbStack DNS OK) 或 http://198.19.x.x 解析到 Ingress IP，看返回 Hello from Flask version v1!。

到此，你没有执行任何 kubectl 命令就完成了初始上线。

⸻

6. 发布 v2 （金丝雀）通过 GitOps

现在要将 “v1” 升级到 “v2”。你只要修改 Rollout YAML 中的 image 字段，然后 push 到配置仓库，Argo CD 会自动发现变化 => 应用到集群 => 触发 Argo Rollouts 金丝雀过程。具体操作如下：
	1.	更新 config repo

# 在本地克隆 my-flask-app-config
git clone https://github.com/YourOrg/my-flask-app-config.git
cd my-flask-app-config

# 修改 rollout.yaml
# 将 image: myflask:v1 改成 image: myflask:v2
# 也可以改 steps if you like
vim rollout.yaml

git commit -am "Update to myflask:v2 for canary release"
git push


	2.	Argo CD检测到变更
如果你在“自动同步”模式下，Argo CD 会立即 re-sync；若是手动同步，你需要在Argo CD UI “Sync”按钮点击一次。
	3.	Argo Rollouts 在集群内执行：
	•	启动 canary Pod (v2), setWeight=20 => 20% 流量 => pause 30s => 100% => remove v1。
	4.	访问测试
再 curl http://flask-gitops.docker。在 pause 20%期间，约1~2成请求返回v2，其余v1；30秒后全v2。

如果 v2 出现故障，你可以回滚——只需在 config repo revert commit 或修改 image 回到 myflask:v1，push。Argo CD 看到又改回 v1，会再次触发 Rollout 变更 => 回退到老版本 Pod。

⸻

7. 观察金丝雀过程

7.1 Argo CD UI
	•	在 Applications -> flask-gitops 中查看资源状态，会看到 Rollout/flask-rollout 改变，Pods 逐步替换。
	•	你还可以点进“Live Manifest”里看 spec.strategy.canary steps 之类，或 Events 了解 Pod 启动时间。

7.2 Argo Rollouts Dashboard (可选)

如果你想查看更细节——比如金丝雀 Step 进度、Pause 倒计时等，安装 Argo Rollouts Dashboard：

kubectl apply -n argo-rollouts -f \
  https://raw.githubusercontent.com/argoproj/argo-rollouts/stable/manifests/dashboard-install.yaml
kubectl port-forward -n argo-rollouts svc/argo-rollouts-dashboard 3100:80

浏览器访问 http://localhost:3100，找到 flask-rollout。你能看到金丝雀 20% -> pause -> 100% 的具体过程，并可点“Abort”中止。一切都在浏览器UI上完成，无需命令行。

⸻

8. 多环境 / 审批流程

在真实生产，你可能有更多需求：
	1.	多环境：
	•	可能有 dev / staging / production 三个目录或 Git 分支，各自有 rollout.yaml 的配置信息(如副本数、镜像tag等)。
	•	Argo CD 可以创建多个 Application 或用 “App of Apps” 模式管理多环境。
	2.	审批：
	•	在进入生产前，需要团队主管审批 Merge Request；Git 里做 Pull Request + Code Review + Approve，才能合并到 prod 分支，引发 Argo CD 同步到生产集群。
	3.	自动回滚：
	•	可在 rollout.yaml 里加入 analysis:，让 Argo Rollouts监测 Prometheus metrics，如果失败就回滚。
	4.	进一步安全：
	•	生产集群只允许 Argo CD (在 cluster 内) 拥有写权限，其它人仅能访问 Argo CD UI + Git 仓库 => 确保不直接 kubectl 上生产。

这些都可以在 GitOps 体系下顺利扩展，而无需在生产命令行执行任何指令。

⸻

9. 小结
	•	Argo CD + Argo Rollouts + Config Repo 的组合，即GitOps式金丝雀发布：
	1.	Config Repo：存放 Rollout.yaml, Service.yaml, Ingress.yaml 等 K8s 资源；
	2.	Argo CD：持续监测此仓库，一旦发现 YAML 变更（如 image: myflask:v2），自动同步到集群；
	3.	Argo Rollouts：在集群内执行金丝雀 / 蓝绿策略，自动或人工 Pause, 失败自动回滚；
	4.	过程无需手动输入命令行 kubectl、helm upgrade 等；所有操作可在Git 或在 Argo CD UI 中完成；
	5.	回滚同理，在 Git revert 旧提交或修改 image: myflask:v1 即可。

这正是生产环境中无命令行、可审计、可回滚的最佳实践之一。通过本教程，你可以一步步在 OrbStack 上复现：
	•	安装 Argo CD + Argo Rollouts
	•	配置 GitOps
	•	编写 Rollout YAML
	•	提交 不同镜像版本到 Git
	•	Argo CD 自动部署 + 金丝雀
	•	UI（Argo CD / Rollouts Dashboard）观察与控制

如果你还想自动构建镜像(“v2”)并更新 rollout.yaml，可以在 CI（TeamCity/Jenkins/GitLab CI）完成后脚本化推送修改到 config repo，这样形成端到端 CI→CD→运行。一切无手动命令行。祝你在生产环境中大获成功！