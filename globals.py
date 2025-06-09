from utilities.metadata import find_metadata_files

class _Components:
    def __init__(self):
        self.datasets = {}
        self.pipelines = {}
        self.services = {}
        self.scripts = {}
        self.models = {}

    def scan_all(self):
        available_components = find_metadata_files()
        self.datasets = available_components.get("dataset", {})
        self.pipelines = available_components.get("pipeline", {})
        self.services = available_components.get("service", {})
        self.scripts = available_components.get("script", {})
        self.models = available_components.get("model", {})

components = _Components()