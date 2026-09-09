ALERTS = {
    "HighCPUUsage": {
        "payload": {
            "labels": {
                "alertname": "HighCPUUsage",
                "component": "remote_write",
                "instance": "localhost:3030",
                "job": "collector_binary",
                "severity": "critical",
                "pod_name": "prom-74cbfb46c9-2ftk9",
                "service": "metrics-pipeline",
            },
            "annotations": {
                "summary": "CPU usage is over 90%",
                "description": "Pod CPU has exceeded the critical threshold",
                "ruleid": "32bb3fbe-c10b-44bb-a4c0-3d053f4a08cd",
                "monitor_slug": "test-monitor",
                "notification_policy_slug": "test-policy",
            },
        },
        "parameters": {
            "labels.host": ["host1", "host2", "host3"],
            "labels.service": [
                "api",
                "queue",
                "db",
                "metrics-pipeline",
                "collector",
            ],
            "labels.instance": ["instance1", "instance2", "instance3"],
        },
    },
    "DiskSpaceLow": {
        "payload": {
            "labels": {
                "alertname": "DiskSpaceLow",
                "severity": "warning",
                "job": "node_exporter",
                "instance": "node-1:9100",
            },
            "annotations": {
                "summary": "Disk space is below 20%",
                "description": "Root volume free space is critically low",
                "monitor_slug": "disk-monitor",
                "notification_policy_slug": "default-policy",
            },
        },
        "parameters": {
            "labels.host": ["host1", "host2", "host3"],
            "labels.service": ["api", "db", "cache"],
            "labels.instance": ["instance1", "instance2", "instance3"],
        },
    },
    "NetworkLatencyHigh": {
        "payload": {
            "labels": {
                "alertname": "NetworkLatencyHigh",
                "severity": "info",
                "component": "ingress",
            },
            "annotations": {
                "summary": "Network latency is higher than normal",
                "monitor_slug": "latency-monitor",
                "notification_policy_slug": "info-policy",
            },
        },
        "parameters": {
            "labels.host": ["host1", "host2"],
            "labels.service": ["edge", "api-gateway"],
        },
    },
}
