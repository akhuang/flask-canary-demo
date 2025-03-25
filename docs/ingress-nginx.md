# Ingress-Nginx Configuration Guide

## Overview
This document outlines the Ingress-Nginx configuration for our Flash Sale system, focusing on traffic routing, load balancing, and canary deployment integration.

## Traffic Flow Architecture
```mermaid
graph TD
    Client[Client] -->|HTTP/HTTPS| ELB[External Load Balancer]
    ELB -->|Forward| Ingress[Ingress-Nginx Controller]
    
    subgraph "Kubernetes Cluster"
        Ingress -->|Weight: 90%| StableSvc[Stable Service]
        Ingress -->|Weight: 10%| CanarySvc[Canary Service]
        
        StableSvc -->|Route| StablePod1[Stable Pod 1]
        StableSvc -->|Route| StablePod2[Stable Pod 2]
        CanarySvc -->|Route| CanaryPod1[Canary Pod 1]
        CanarySvc -->|Route| CanaryPod2[Canary Pod 2]
    end
```

## Request Processing Flow
```mermaid
sequenceDiagram
    participant C as Client
    participant I as Ingress
    participant S as Stable Service
    participant Ca as Canary Service
    participant P as Pods
    
    C->>I: HTTP Request
    I->>I: Apply Rate Limiting
    I->>I: TLS Termination
    
    alt Headers Match Canary
        I->>Ca: Route to Canary
        Ca->>P: Forward to Canary Pods
    else Standard Traffic
        I->>S: Route to Stable
        S->>P: Forward to Stable Pods
    end
```

## Configuration Layers
```mermaid
graph TD
    A[Ingress Config] --> B[TLS Config]
    A --> C[Route Rules]
    A --> D[Annotations]
    
    B --> B1[Certificates]
    B --> B2[SSL Policies]
    
    C --> C1[Path Rules]
    C --> C2[Host Rules]
    C --> C3[Service Mapping]
    
    D --> D1[Rate Limiting]
    D --> D2[Canary Rules]
    D --> D3[CORS Policy]
```

## Rate Limiting Structure
```mermaid
flowchart TD
    A[Request] --> B{Check Rate Limit}
    B -->|Within Limit| C[Process Request]
    B -->|Exceeded| D[Return 429]
    
    C --> E{Resource Available?}
    E -->|Yes| F[Return Response]
    E -->|No| G[Return 503]
```

## SSL/TLS Flow
```mermaid
sequenceDiagram
    participant Client
    participant Ingress
    participant Backend
    
    Client->>Ingress: HTTPS Request
    Ingress->>Ingress: TLS Termination
    Ingress->>Backend: HTTP Request
    Backend->>Ingress: HTTP Response
    Ingress->>Ingress: TLS Wrapping
    Ingress->>Client: HTTPS Response
```

## Canary Rules Processing
```mermaid
graph TD
    A[Incoming Request] --> B{Check Headers}
    B -->|Canary Headers| C[Canary Service]
    B -->|No Headers| D{Weight-based}
    D -->|10%| C
    D -->|90%| E[Stable Service]
```

## Health Check Flow
```mermaid
sequenceDiagram
    participant HC as Health Checker
    participant Svc as Service
    participant Pod as Pod
    
    loop Every 5 seconds
        HC->>Svc: Health Check Request
        Svc->>Pod: Forward Check
        Pod->>Svc: Health Status
        Svc->>HC: Return Status
        
        alt Healthy
            HC->>HC: Keep in Pool
        else Unhealthy
            HC->>HC: Remove from Pool
        end
    end
```

## Load Balancing Strategies
```mermaid
graph TD
    A[Load Balancer] --> B{Algorithm}
    B -->|Round Robin| C[Equal Distribution]
    B -->|IP Hash| D[Session Affinity]
    B -->|Least Conn| E[Least Connections]
    
    C --> F[Pod Pool]
    D --> F
    E --> F
```

## Performance Optimization
```mermaid
flowchart TD
    A[Optimization Areas] --> B[Connection Handling]
    A --> C[SSL Configuration]
    A --> D[Buffer Settings]
    
    B --> B1[Keep-alive]
    B --> B2[Timeouts]
    
    C --> C1[Session Cache]
    C --> C2[OCSP Stapling]
    
    D --> D1[Client Body]
    D --> D2[Proxy Buffer]
```

## Best Practices

### 1. Configuration Structure
```mermaid
graph LR
    A[Base Config] --> B[Environment Specific]
    B --> C[Service Specific]
    C --> D[Path Specific]
```

### 2. Security Layers
```mermaid
graph TD
    A[Security] --> B[TLS]
    A --> C[Rate Limiting]
    A --> D[CORS]
    A --> E[WAF Rules]
```

## Monitoring Setup
```mermaid
graph TD
    A[Metrics] --> B[Request Rate]
    A --> C[Error Rate]
    A --> D[Latency]
    A --> E[Connection Stats]
    
    B --> F[Prometheus]
    C --> F
    D --> F
    E --> F
    
    F --> G[Grafana Dashboard]
```

## Implementation Guidelines
1. Configure proper timeouts and buffer sizes
2. Implement circuit breaking for backend services
3. Set up detailed monitoring and alerting
4. Use proper TLS configuration
5. Implement rate limiting and security policies