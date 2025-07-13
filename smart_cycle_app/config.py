import os
from datetime import datetime

# System Configuration
SHARED_DIR = r"C:\SmartCycle"
OUTPUT_BASE_DIR = os.path.join(SHARED_DIR, 'output')
INPUT_DATA_DIR = os.path.join(SHARED_DIR, 'input_files')
DEFAULT_DATA_DIR = os.path.join(SHARED_DIR, 'default')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models', 'saved')

OUTPUT_DATA_DIR = OUTPUT_BASE_DIR
REPORTS_DIR = os.path.join(OUTPUT_DATA_DIR, 'reports')
PLOTS_DIR = os.path.join(OUTPUT_DATA_DIR, 'plots')


def set_output_folder(folder_name: str) -> str:
    """Create timestamped subfolder under given folder and set as output directory."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_path = os.path.join(OUTPUT_BASE_DIR, folder_name)
    final_path = os.path.join(base_path, timestamp)
    os.makedirs(final_path, exist_ok=True)

    global OUTPUT_DATA_DIR, REPORTS_DIR, PLOTS_DIR
    OUTPUT_DATA_DIR = final_path
    REPORTS_DIR = os.path.join(OUTPUT_DATA_DIR, 'reports')
    PLOTS_DIR = os.path.join(OUTPUT_DATA_DIR, 'plots')
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)
    return OUTPUT_DATA_DIR


def get_user_reports_dir(user_id: str) -> str:
    user_output_dir = os.path.join(OUTPUT_DATA_DIR, user_id)
    return os.path.join(user_output_dir, 'reports')


def get_user_plots_dir(user_id: str) -> str:
    user_output_dir = os.path.join(OUTPUT_DATA_DIR, user_id)
    return os.path.join(user_output_dir, 'plots')

# Legacy global directories
YML_TESTS_DIR = os.path.join(SHARED_DIR, 'yml_files')
