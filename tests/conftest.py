import sys
import os
import importlib.util

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(REPO_ROOT, "hydrography-approach", "processing_scripts", "associate_data"))
sys.path.insert(0, os.path.join(REPO_ROOT, "hydrography-approach", "processing_scripts", "bridge_statistics"))
sys.path.insert(0, os.path.join(REPO_ROOT, "hydrography-approach", "processing_scripts", "filter_data"))
sys.path.insert(0, os.path.join(REPO_ROOT, "merge-approaches"))
sys.path.insert(0, os.path.join(REPO_ROOT, "mile-point-approach"))
sys.path.insert(0, os.path.join(REPO_ROOT, "split-ways-using-JOSM", "obtain_bridge_split_coordinates"))
sys.path.insert(0, os.path.join(REPO_ROOT, "split-ways-using-JOSM", "split_ways_add_bridge_tag"))


def load_module_from_file(name, filepath):
    """Load a Python module from a file path (handles names starting with digits or hyphens)."""
    spec = importlib.util.spec_from_file_location(name, filepath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
