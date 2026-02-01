#!/usr/bin/env python3
"""YAML processing utilities that will fail due to syntax errors"""

import yaml
import os

def load_config():
    """Load configuration from YAML file - will fail due to syntax errors"""
    config_path = ".github/config/broken-config.yml"
    
    try:
        with open(config_path, 'r') as file:
            # This will fail due to YAML syntax errors
            config = yaml.safe_load(file)
            return config
    except yaml.YAMLError as e:
        print(f"YAML Error: {e}")
        raise
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        raise

def validate_workflow():
    """Validate workflow YAML files - will detect syntax errors"""
    workflow_path = ".github/workflows/broken-workflow.yml"
    
    try:
        with open(workflow_path, 'r') as file:
            # This will fail due to workflow YAML syntax errors
            workflow = yaml.safe_load(file)
            return workflow
    except yaml.YAMLError as e:
        print(f"Workflow YAML Error: {e}")
        raise

if __name__ == "__main__":
    print("Loading configuration...")
    config = load_config()
    print(f"Config loaded: {config}")
    
    print("Validating workflow...")
    workflow = validate_workflow()
    print(f"Workflow valid: {workflow}")