"""
Backend Service for Smart Cycle Test Planning System
"""

import os
import sys
import json
import asyncio
import concurrent.futures
import pandas as pd
import logging
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    import streamlit as st
except ImportError:
    class DummyStreamlit:
        def progress(self, value):
            pass
        def text(self, text):
            pass
    st = DummyStreamlit()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from config import INPUT_DATA_DIR, OUTPUT_DATA_DIR, DEFAULT_DATA_DIR, get_user_reports_dir, get_user_plots_dir

from core.orchestrator import Orchestrator  # placeholder for actual import
from utils.chatbot import chatbot  # placeholder for actual import

class SmartCycleBackend:
    def __init__(self, session_id: str = None):
        self.session_id = session_id or "default"
        self.orchestrator = None
        self.current_test_plan = None
        self.current_test_plan_file = None
        self.evaluation_results = None
        self.test_level_data = None
        self.last_processed_files = None
        self.update_output_dir()

    def update_output_dir(self):
        self.session_output_dir = os.path.join(OUTPUT_DATA_DIR, f"session_{self.session_id}")
        os.makedirs(self.session_output_dir, exist_ok=True)

    def get_files_in_directory(self, directory_path: str, extensions: List[str] = None) -> List[str]:
        if extensions is None:
            extensions = ['.csv', '.xlsx', '.xls']
        files = []
        if os.path.exists(directory_path):
            for file in os.listdir(directory_path):
                if any(file.endswith(ext) for ext in extensions):
                    files.append(file)
        return sorted(files)

    def get_folder_structure(self) -> Dict[str, List[str]]:
        structure = {}
        input_base = INPUT_DATA_DIR
        if os.path.exists(input_base):
            structure['input'] = self.get_files_in_directory(input_base)
            for item in os.listdir(input_base):
                item_path = os.path.join(input_base, item)
                if os.path.isdir(item_path):
                    structure[f'input/{item}'] = self.get_files_in_directory(item_path)
        output_base = OUTPUT_DATA_DIR
        if os.path.exists(output_base):
            structure['output'] = self.get_files_in_directory(output_base, ['.json', '.csv'])
            reports_path = os.path.join(output_base, 'reports')
            if os.path.exists(reports_path):
                structure['reports'] = self.get_files_in_directory(reports_path, ['.csv'])
        return structure

    def get_available_eval_files(self) -> List[str]:
        return self.get_files_in_directory(INPUT_DATA_DIR, ['.csv', '.xlsx', '.xls'])

    def get_available_test_plans(self) -> List[str]:
        test_plan_files = []
        output_files = self.get_files_in_directory(self.session_output_dir, ['.json'])
        for file in output_files:
            if 'test_plan' in file.lower():
                test_plan_files.append(file)
        if os.path.exists(DEFAULT_DATA_DIR):
            default_files = self.get_files_in_directory(DEFAULT_DATA_DIR, ['.json'])
            for file in default_files:
                if 'test_plan' in file.lower():
                    test_plan_files.append(f"default/{file}")
        return test_plan_files

    def process_files(self, test_history_file: str, config_file: str, folder: str = "input") -> Dict[str, Any]:
        try:
            base_path = INPUT_DATA_DIR if folder == "input" else os.path.join(INPUT_DATA_DIR, folder)
            test_history_path = os.path.join(base_path, test_history_file)
            config_path = os.path.join(base_path, config_file)
            if not os.path.exists(test_history_path):
                return {"success": False, "error": f"Test history file not found: {test_history_file}"}
            if not os.path.exists(config_path):
                return {"success": False, "error": f"Configuration file not found: {config_file}"}
            self.orchestrator = Orchestrator(
                test_history_path=test_history_path,
                config_info_path=config_path,
                output_path=self.session_output_dir,
            )
            self.last_processed_files = {
                'test_history_file': test_history_file,
                'config_file': config_file,
                'folder': folder,
                'test_history_path': test_history_path,
                'config_path': config_path,
            }
            analysis_data = self.get_analysis_data()
            return {"success": True, "analysis_data": analysis_data}
        except Exception as e:
            logger.error(f"Error processing files: {e}")
            return {"success": False, "error": str(e)}

    async def generate_poa_matrix_async(self) -> Dict[str, Any]:
        try:
            if self.orchestrator is None:
                return {"success": False, "error": "No files processed yet."}
            loop = asyncio.get_event_loop()
            test_plan = await loop.run_in_executor(None, self.orchestrator.generate_test_plan)
            self.current_test_plan = test_plan
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"test_plan_{self.session_id}_{timestamp}.json"
            filepath = os.path.join(self.session_output_dir, filename)
            await loop.run_in_executor(None, self._save_test_plan_sync, test_plan, filepath)
            self.current_test_plan_file = filepath
            return {"success": True, "filename": filename, "test_plan": test_plan}
        except Exception as e:
            logger.error(f"Error generating POA matrix: {e}")
            return {"success": False, "error": str(e)}

    def _save_test_plan_sync(self, test_plan: Dict[str, Any], filepath: str):
        with open(filepath, 'w') as f:
            json.dump(test_plan, f, indent=2)

    def load_existing_poa_matrix(self, filename: str) -> Dict[str, Any]:
        try:
            if filename.startswith("default/"):
                actual_filename = filename[8:]
                filepath = os.path.join(DEFAULT_DATA_DIR, actual_filename)
            else:
                filepath = os.path.join(self.session_output_dir, filename)
            if not os.path.exists(filepath):
                return {"success": False, "error": f"File not found: {filename}"}
            with open(filepath, 'r') as f:
                test_plan = json.load(f)
            self.current_test_plan = test_plan
            self.current_test_plan_file = filepath
            return {"success": True, "test_plan": test_plan}
        except Exception as e:
            logger.error(f"Error loading POA matrix: {e}")
            return {"success": False, "error": str(e)}

    async def run_evaluation_async(self, eval_file: str) -> Dict[str, Any]:
        try:
            if self.current_test_plan is None:
                return {"success": False, "error": "No test plan available."}
            if self.current_test_plan_file is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                temp_file = os.path.join(self.session_output_dir, f"temp_test_plan_{timestamp}.json")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._save_test_plan_sync, self.current_test_plan, temp_file)
                self.current_test_plan_file = temp_file
            loop = asyncio.get_event_loop()
            self.evaluation_results = await loop.run_in_executor(None, self._run_evaluation_sync, eval_file)
            if self.evaluation_results and 'test_level_report' in self.evaluation_results:
                test_level_data = self.evaluation_results['test_level_report']
                if isinstance(test_level_data, list):
                    self.test_level_data = pd.DataFrame(test_level_data)
                else:
                    self.test_level_data = test_level_data
            else:
                self._load_latest_test_level_report()
            return {"success": True, "evaluation_results": self.evaluation_results}
        except Exception as e:
            logger.error(f"Error running evaluation: {e}")
            return {"success": False, "error": str(e)}

    def _run_evaluation_sync(self, eval_file: str):
        from evaluation.eval_results import generate_comprehensive_evaluation_report_with_testplan
        user_reports_dir = get_user_reports_dir(self.session_id)
        return generate_comprehensive_evaluation_report_with_testplan(
            eval_data_file=eval_file,
            test_plan=self.current_test_plan,
            reports_dir=user_reports_dir,
        )

    def _load_latest_test_level_report(self):
        try:
            reports_dir = get_user_reports_dir(self.session_id)
            if os.path.exists(reports_dir):
                test_level_files = [f for f in os.listdir(reports_dir) if f.startswith('test_level_evaluation_')]
                if test_level_files:
                    latest_file = os.path.join(reports_dir, max(test_level_files))
                    self.test_level_data = pd.read_csv(latest_file)
        except Exception as e:
            logger.error(f"Error loading test level report: {e}")

    def get_analysis_data(self, progress_callback=None) -> Dict[str, Any]:
        if self.orchestrator is None:
            return {"error": "No data processed yet"}
        analysis_data = {}
        try:
            analysis_data['poa_data'] = self.orchestrator.analysis_engine.analyze_poa_correlation()
            analysis_data['failure_data'] = self.orchestrator.analysis_engine.analyze_failures_by_cycle()
            analysis_data['feature_data'] = self.orchestrator.analysis_engine.analyze_feature_effectiveness()
            return analysis_data
        except Exception as e:
            logger.error(f"Error during analysis: {e}")
            return {"error": str(e)}

    def get_general_statistics(self) -> Dict[str, Any]:
        if self.orchestrator is None:
            return {"error": "No data processed yet"}
        test_df = self.orchestrator.analysis_engine.test_history_df
        config_df = self.orchestrator.analysis_engine.config_info_df
        if test_df is None or config_df is None:
            return {"error": "No data available"}
        total_cycles = test_df['cycle_id'].nunique() if 'cycle_id' in test_df.columns else 0
        total_executions = len(test_df)
        total_tests = test_df['test_key'].nunique() if 'test_key' in test_df.columns else 0
        failed_tests = test_df[test_df['status'] == 'fail']['test_key'].nunique() if 'test_key' in test_df.columns else 0
        total_configs = len(config_df)
        status_counts = test_df['status'].value_counts().to_dict() if 'status' in test_df.columns else {}
        return {
            'total_cycles': total_cycles,
            'total_executions': total_executions,
            'total_tests': total_tests,
            'failed_tests': failed_tests,
            'total_configs': total_configs,
            'status_counts': status_counts,
        }

    def get_backend_status(self) -> Dict[str, Any]:
        return {
            'orchestrator_initialized': self.orchestrator is not None,
            'current_test_plan_exists': self.current_test_plan is not None,
            'current_test_plan_file': self.current_test_plan_file,
            'evaluation_results_exists': self.evaluation_results is not None,
            'test_level_data_exists': self.test_level_data is not None,
            'last_processed_files': self.last_processed_files,
        }

    def force_reinitialize(self, test_history_file: str, config_file: str, folder: str = "input") -> Dict[str, Any]:
        self.orchestrator = None
        self.current_test_plan = None
        self.current_test_plan_file = None
        self.evaluation_results = None
        self.test_level_data = None
        self.last_processed_files = None
        self.update_output_dir()
        return self.process_files(test_history_file, config_file, folder)

class BackendManager:
    _instances = {}
    _lock = threading.Lock()
    _session_last_access = {}

    @classmethod
    def get_backend(cls, session_id: str) -> SmartCycleBackend:
        with cls._lock:
            if session_id not in cls._instances:
                cls._instances[session_id] = SmartCycleBackend(session_id)
            cls._session_last_access[session_id] = datetime.now()
            return cls._instances[session_id]

    @classmethod
    def cleanup_session(cls, session_id: str):
        with cls._lock:
            if session_id in cls._instances:
                del cls._instances[session_id]
            if session_id in cls._session_last_access:
                del cls._session_last_access[session_id]

backend_manager = BackendManager()
