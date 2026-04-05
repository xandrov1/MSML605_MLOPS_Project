# Connect to clearML and read project data like:
# Model architecture/name
# Dataset info (size, type)
# Hyperparameters
# Performance metrics (loss, accuracy etc.)
# Runtime

from clearml import Task
from dotenv import load_dotenv
import os

load_dotenv() # Check .env for clearml credentials

def get_task_data(project_name, task_name): # Gets clearML task info
    task = Task.get_task(project_name=project_name, task_name=task_name)
    
    # Basic info
    print("Task ID:", task.id)
    print("Task name:", task.name)
    print("Status:", task.status)
    
    # Hyperparameters
    print("\nHyperparameters:")
    params = task.get_parameters()
    for k, v in params.items():
        print(f"  {k}: {v}")
    
    # Metrics
    print("\nMetrics:")
    metrics = task.get_last_scalar_metrics()
    for metric, variants in metrics.items():
        for variant, values in variants.items():
            print(f"  {metric}/{variant}: {values['last']}")
    
    return task

if __name__ == "__main__":
    get_task_data("605_HW2", "FashionMNIST_CNN_training")