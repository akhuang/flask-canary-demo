# flask-canary-demo
 
http://flask-v1-svc.default.svc.cluster.local/
http://flask-v2-svc.default.svc.cluster.local/


admin
mzxyEP56eN5TOukN


docker run --rm -l dev.orbstack.domains=foo.local,bar.local nginx

docker run --rm -l dev.orbstack.domains=foo.local,bar.local,flask-gitops.local nginx


cd my-flask-app
docker build -t myflask:v1 --build-arg FLASK_VERSION=v1 .
docker build -t myflask:v2 --build-arg FLASK_VERSION=v2 .

docker build -t myflask:v2.4.5 --build-arg FLASK_VERSION=v2.4.5 .


https://gitops.k8s.orb.local/


for i in {1..10}; do curl -s https://gitops.k8s.orb.local/; done


for i in {1..10}; do curl -s https://bluegreen.k8s.orb.local/; done
for i in {1..10}; do curl -s https://preview.bluegreen.k8s.orb.local/; done
