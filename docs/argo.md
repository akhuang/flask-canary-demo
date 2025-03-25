# Argo Rollouts Guide

## Overview
This document describes the canary deployment and progressive delivery strategy using Argo Rollouts for our Flash Sale system.

## Architecture
```mermaid
graph TD
    Client[Client] -->|Request| Ingress[Ingress Controller]
    Ingress -->|Traffic Split| Service[Service]
    Service -->|Current Version| Stable[Stable Version]
    Service -->|Canary Version| Canary[Canary Version]
    
    subgraph "Kubernetes Cluster"
        Ingress
        Service
        Stable
        Canary
    end
```

## Canary Deployment Flow
```mermaid
sequenceDiagram
    participant User as User
    participant IC as Ingress Controller
    participant Svc as Service
    participant Stable as Stable Version
    participant Canary as Canary Version
    participant Metrics as Metrics Server
    
    User->>IC: HTTP Request
    IC->>Svc: Route Traffic
    
    alt 90% Traffic
        Svc->>Stable: Route to Stable
    else 10% Traffic
        Svc->>Canary: Route to Canary
    end
    
    Metrics->>Canary: Collect Metrics
    Metrics->>Stable: Collect Metrics
```

## Progressive Delivery Steps
```mermaid
graph LR
    A[Deploy] --> B[10% Traffic]
    B --> C{Health Check}
    C -->|Pass| D[30% Traffic]
    C -->|Fail| E[Rollback]
    D --> F{Health Check}
    F -->|Pass| G[50% Traffic]
    F -->|Fail| E
    G --> H{Health Check}
    H -->|Pass| I[100% Traffic]
    H -->|Fail| E
```

## Rollout Configuration Structure
```mermaid
graph TD
    A[Rollout Config] --> B[Deployment Strategy]
    A --> C[Service Reference]
    A --> D[Replicas]
    
    B --> E[Canary]
    E --> F[Steps]
    F --> G[Traffic Weight]
    F --> H[Pause Duration]
    F --> I[Health Checks]
```

## Health Check Flow
```mermaid
sequenceDiagram
    participant Argo as Argo Controller
    participant Pod as Pod
    participant Metrics as Metrics
    
    loop Every Check Interval
        Argo->>Pod: Health Check Request
        Pod->>Metrics: Query Metrics
        Metrics->>Argo: Return Results
        
        alt Metrics Pass
            Argo->>Argo: Proceed to Next Step
        else Metrics Fail
            Argo->>Argo: Initiate Rollback
        end
    end
```

## Rollback Process
```mermaid
flowchart TD
    A[Detect Issue] --> B{Automatic Rollback?}
    B -->|Yes| C[Stop Canary Traffic]
    B -->|No| D[Manual Intervention]
    C --> E[Scale Down Canary]
    E --> F[Route All Traffic to Stable]
    D --> G[Operator Decision]
    G -->|Rollback| C
    G -->|Continue| H[Monitor and Proceed]
```

## Metrics and Analysis
```mermaid
graph TD
    A[Prometheus] -->|Collect| B[Pod Metrics]
    A -->|Collect| C[Request Metrics]
    A -->|Collect| D[Business Metrics]
    
    B --> E[Analysis]
    C --> E
    D --> E
    
    E -->|Pass/Fail| F[Rollout Decision]
```

## Best Practices
1. **Gradual Traffic Shifting**
```mermaid
graph LR
    A[10%] --> B[30%]
    B --> C[50%]
    C --> D[80%]
    D --> E[100%]
```

2. **Monitoring Points**
```mermaid
graph TD
    A[Monitor Points] --> B[Error Rate]
    A --> C[Latency]
    A --> D[Success Rate]
    A --> E[Business Metrics]
```

## Failure Scenarios
```mermaid
flowchart TD
    A[Detect Failure] --> B{Failure Type}
    B -->|Error Rate High| C[Instant Rollback]
    B -->|Latency High| D[Scale Up]
    B -->|Memory Leak| E[Restart Pods]
    
    C --> F[Post-mortem]
    D --> F
    E --> F
```

## Deployment Strategy
1. Start with minimal traffic (10%)
2. Monitor key metrics
3. Gradually increase traffic
4. Automatic rollback on failure
5. Complete promotion after all checks pass