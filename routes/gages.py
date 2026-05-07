from flask import Blueprint, Response
import subprocess
import psutil
import time
import json

gages_blueprint = Blueprint('gages', __name__)

def get_gpu_stats():
    while True:
        try:
            gpu_stats = []
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                gpu_data = result.stdout.strip().split("\n")
                gpu_stats = [
                    dict(zip(["gpu_usage", "memory_used", "memory_total"], line.split(", ")))
                    for line in gpu_data
                ]

            yield f"data: {json.dumps(gpu_stats)}\n\n"
        except Exception as e:
            yield f"data: Error fetching GPU stats: {str(e)}\n\n"

        time.sleep(2)

@gages_blueprint.route('/gpu')
def gpu_stream():
    return Response(get_gpu_stats(), content_type='text/event-stream')


def get_cpu_stats():
    while True:
        try:
            cpu_stats = {
                "cpu_usage": psutil.cpu_percent(interval=None),
                "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else None,
                "cpu_cores": psutil.cpu_count(logical=False),
                "cpu_threads": psutil.cpu_count(logical=True)
            }
            yield f"data: {json.dumps(cpu_stats)}\n\n"
        except Exception as e:
            yield f"data: Error fetching CPU stats: {str(e)}\n\n"

        time.sleep(2)

@gages_blueprint.route('/cpu')
def cpu_stream():
    return Response(get_cpu_stats(), content_type='text/event-stream')
