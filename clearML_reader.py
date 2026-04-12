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
    if task is None:
        raise ValueError(f"Task '{task_name}' not found in project '{project_name}'")
    
    metrics = task.get_last_scalar_metrics()
    
    # Separate machine metrics from model metrics
    machine_metrics = {}
    model_metrics = {}
    for metric, variants in metrics.items():
        for variant, values in variants.items():
            if ':monitor:machine' in metric:
                machine_metrics[f"{metric}/{variant}"] = values['last']
            else:
                model_metrics[f"{metric}/{variant}"] = values['last']
    
    return {
        'id': task.id,
        'name': task.name,
        'status': task.status,
        'hyperparameters': task.get_parameters(),
        'model_metrics': model_metrics,
        'machine_metrics': machine_metrics
    }