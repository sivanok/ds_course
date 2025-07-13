import os
import sys
import asyncio
import concurrent.futures
import pandas as pd
import logging
import json
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import Dict, Any, List
import threading
import time
import uuid
from config import POA_CORR_CYCLES, SHARED_DIR, INPUT_DATA_DIR, OUTPUT_DATA_DIR, AVAILABLE_MODELS, set_active_model, get_current_model_info, set_output_folder, OUTPUT_BASE_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_async_in_streamlit(coro):
    try:
        logger.info(f"Running async function: {coro}")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            result = future.result()
            logger.info(f"Async function completed successfully")
            return result
    except Exception as e:
        error_msg = f"Async operation failed: {e}"
        st.error(error_msg)
        logger.error(error_msg)
        return None

class StreamlitLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_records = []
        self.lock = threading.Lock()
        self.max_records = 50
    def emit(self, record):
        if record.name.startswith(('streamlit', 'matplotlib', 'urllib3', 'requests')):
            return
        try:
            with self.lock:
                formatted_record = self.format(record)
                self.log_records.append(formatted_record)
                if len(self.log_records) > self.max_records:
                    self.log_records = self.log_records[-self.max_records:]
        except Exception:
            pass
    def get_logs(self):
        with self.lock:
            return self.log_records.copy()
    def clear_logs(self):
        with self.lock:
            self.log_records.clear()

if 'log_handler' not in st.session_state:
    st.session_state.log_handler = StreamlitLogHandler()
    st.session_state.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

def simple_log_display(log_container, message):
    try:
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_container.text(f"📝 {timestamp} - {message}")
        time.sleep(0.1)
    except Exception:
        pass

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from backend_service import backend_manager

@st.cache_resource
def get_session_backend():
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return backend_manager.get_backend(st.session_state.session_id)

backend = get_session_backend()

st.set_page_config(
    page_title="Smart Cycle - Test Planning System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 36px;
        font-weight: bold;
        color: #1E88E5;
        margin-bottom: 20px;
    }
    .section-header {
        font-size: 24px;
        font-weight: bold;
        color: #1976D2;
        margin-top: 30px;
        margin-bottom: 10px;
    }
    .stButton>button {
        background-color: #1976D2;
        color: white;
        font-weight: bold;
        border-radius: 5px;
        padding: 10px 20px;
        width: 100%;
    }
    .workflow-step {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
    .step-completed {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
    }
    .step-current {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
    }
    .step-pending {
        background-color: #f8f9fa;
        border-left: 5px solid #6c757d;
    }
    .log-container {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        max-height: 300px;
        overflow-y: auto;
    }
    .chat-button {
        position: fixed;
        top: 80px;
        right: 20px;
        z-index: 999;
        background-color: #28a745;
        color: white;
        border: none;
        border-radius: 50px;
        padding: 12px 20px;
        font-weight: bold;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transition: all 0.3s ease;
    }
    .chat-button:hover {
        background-color: #218838;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.2);
    }
    .chat-container {
        position: fixed;
        top: 100px;
        right: 20px;
        width: 400px;
        max-height: 600px;
        background: white;
        border-radius: 10px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        border: 1px solid #e1e8ed;
        z-index: 1000;
        display: none;
    }
    .chat-header {
        background-color: #28a745;
        color: white;
        padding: 15px;
        border-radius: 10px 10px 0 0;
        font-weight: bold;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .chat-messages {
        height: 400px;
        overflow-y: auto;
        padding: 15px;
        border-bottom: 1px solid #e1e8ed;
    }
    .chat-input-area {
        padding: 15px;
        border-radius: 0 0 10px 10px;
    }
    .message {
        margin-bottom: 15px;
        padding: 10px;
        border-radius: 10px;
        max-width: 85%;
    }
    .message-user {
        background-color: #007bff;
        color: white;
        margin-left: auto;
        text-align: right;
    }
    .message-bot {
        background-color: #f8f9fa;
        color: #333;
        border: 1px solid #e1e8ed;
    }
</style>
""", unsafe_allow_html=True)

# session state initialization
if 'workflow_step' not in st.session_state:
    st.session_state.workflow_step = 1
if 'files_loaded' not in st.session_state:
    st.session_state.files_loaded = False
if 'files_processed' not in st.session_state:
    st.session_state.files_processed = False
if 'poa_matrix_ready' not in st.session_state:
    st.session_state.poa_matrix_ready = False
if 'evaluation_completed' not in st.session_state:
    st.session_state.evaluation_completed = False
if 'publish_completed' not in st.session_state:
    st.session_state.publish_completed = False
if 'initial_statistics' not in st.session_state:
    st.session_state.initial_statistics = None
if 'filter_options' not in st.session_state:
    st.session_state.filter_options = None
if 'applied_filters' not in st.session_state:
    st.session_state.applied_filters = {}
if 'analysis_data' not in st.session_state:
    st.session_state.analysis_data = None
if 'test_plan' not in st.session_state:
    st.session_state.test_plan = None
if 'evaluation_results' not in st.session_state:
    st.session_state.evaluation_results = None
if 'processed_file_info' not in st.session_state:
    st.session_state.processed_file_info = None
if 'show_logs' not in st.session_state:
    st.session_state.show_logs = True
if 'publish_results' not in st.session_state:
    st.session_state.publish_results = None
if 'chat_open' not in st.session_state:
    st.session_state.chat_open = False
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'current_data_file' not in st.session_state:
    st.session_state.current_data_file = None
if 'output_folder_set' not in st.session_state:
    st.session_state.output_folder_set = False
if 'selected_output_base' not in st.session_state:
    st.session_state.selected_output_base = None

def chat_with_data_interface():
    current_file = st.session_state.current_data_file
    if not current_file:
        st.warning("⚠️ No data file selected. Please load files first.")
        return
    st.markdown(f"### 💬 Chat with Data: {current_file}")
    st.markdown("Ask questions about your test data, get analysis, create visualizations, and discover patterns.")
    if st.session_state.chat_messages:
        for i, message in enumerate(st.session_state.chat_messages):
            if message["role"] == "user":
                st.markdown(f"""
                <div style="text-align: right; margin: 10px 0;">
                    <div style="background-color: #007bff; color: white; padding: 10px; border-radius: 10px; display: inline-block; max-width: 80%;">
                        {message["content"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                content = message["content"]
                if isinstance(content, dict):
                    st.markdown(f"""
                    <div style="text-align: left; margin: 10px 0;">
                        <div style="background-color: #f8f9fa; border: 1px solid #e1e8ed; padding: 10px; border-radius: 10px; max-width: 90%;">
                            🤖 <strong>Analysis:</strong> {content.get('description', 'No description')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    result = content.get('result')
                    if isinstance(result, pd.DataFrame):
                        st.dataframe(result, use_container_width=True)
                    elif isinstance(result, pd.Series):
                        st.dataframe(result.to_frame(), use_container_width=True)
                    elif result and str(result) != "No result variable found in the generated code.":
                        st.write(f"**Result:** {result}")
                    plot_path = content.get('plot_path')
                    if plot_path and os.path.exists(plot_path):
                        st.image(plot_path, caption="Generated Visualization")
                        try:
                            os.remove(plot_path)
                        except:
                            pass
                else:
                    st.markdown(f"""
                    <div style="text-align: left; margin: 10px 0;">
                        <div style="background-color: #f8f9fa; border: 1px solid #e1e8ed; padding: 10px; border-radius: 10px; display: inline-block; max-width: 80%;">
                            🤖 {content}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("👋 Start a conversation! Ask me anything about your test data. Examples:")
        st.markdown("""
        - "How many tests are hardware dependent?"
        - "Show me failure trends by platform"
        - "Which tests have the highest failure rates?"
        - "Create a chart of test status distribution"
        - "Find tests that consistently pass across all configurations"
        """)
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_area("Your message:", placeholder="Ask about test patterns, failure analysis, visualizations...")
        col1, col2 = st.columns([3, 1])
        with col1:
            submit_button = st.form_submit_button("Send 💬", use_container_width=True)
        with col2:
            if st.form_submit_button("Clear Chat", use_container_width=True):
                st.session_state.chat_messages = []
                st.rerun()
    if submit_button and user_input.strip():
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with st.spinner("🤔 Analyzing your data..."):
            try:
                chat_result = run_async_in_streamlit(backend.chat_with_data_async(user_input))
                if chat_result['success']:
                    response_content = {
                        'description': chat_result['description'],
                        'result': chat_result['result'],
                        'plot_path': chat_result['plot_path']
                    }
                    st.session_state.chat_messages.append({"role": "assistant", "content": response_content})
                else:
                    error_message = chat_result.get('error', 'Unknown error occurred')
                    st.session_state.chat_messages.append({"role": "assistant", "content": f"I apologize, but I encountered an error: {error_message}"})
                st.rerun()
            except Exception as e:
                error_response = f"I apologize, but I encountered an error while processing your question: {str(e)}. Please try rephrasing your question or check if the data is loaded correctly."
                st.session_state.chat_messages.append({"role": "assistant", "content": error_response})
                st.rerun()

def update_current_data_file():
    if st.session_state.processed_file_info:
        file_info = st.session_state.processed_file_info
        st.session_state.current_data_file = file_info.get('test_history_file', 'Unknown file')

st.sidebar.markdown('<div class="main-header">Smart Cycle</div>', unsafe_allow_html=True)
st.sidebar.markdown("#### Test Planning System")

st.sidebar.markdown("### 🤖 LLM Model Selection")
model_options = []
model_mapping = {}
for key, model_info in AVAILABLE_MODELS.items():
    display_text = f"{model_info['display_name']} - {model_info['description']}"
    model_options.append(display_text)
    model_mapping[display_text] = key
current_model_info = get_current_model_info()
current_display = f"{AVAILABLE_MODELS[current_model_info['key']]['display_name']} - {AVAILABLE_MODELS[current_model_info['key']]['description']}"
selected_model_display = st.sidebar.selectbox(
    "Choose LLM Model:",
    options=model_options,
    index=model_options.index(current_display),
    help="Select the AI model to use for test planning and analysis"
)
selected_model_key = model_mapping[selected_model_display]
if selected_model_key != current_model_info['key']:
    if set_active_model(selected_model_key):
        st.sidebar.success(f"✅ Model updated to {AVAILABLE_MODELS[selected_model_key]['display_name']}")
    else:
        st.sidebar.error("❌ Failed to update model")
current_model = AVAILABLE_MODELS[get_current_model_info()['key']]
st.sidebar.info(f"**Current Model:** {current_model['display_name']}\n\n{current_model['description']}")

# Output folder selection
st.sidebar.markdown("### 📁 Output Folder")
existing_output_bases = [d for d in os.listdir(OUTPUT_BASE_DIR) if os.path.isdir(os.path.join(OUTPUT_BASE_DIR, d))]
selected_base = st.sidebar.selectbox("Select base folder", existing_output_bases, index=0 if existing_output_bases else None)
new_base = st.sidebar.text_input("Or create new base folder", key="new_output_base")
if st.sidebar.button("Set Output Folder"):
    base_folder = new_base.strip() if new_base else selected_base
    if not base_folder:
        st.sidebar.error("Please specify a folder name")
    else:
        output_path = set_output_folder(base_folder)
        backend.update_output_dir()
        st.session_state.output_folder_set = True
        st.session_state.selected_output_base = base_folder
        st.sidebar.success(f"Output folder set: {output_path}")
        st.rerun()
if st.session_state.output_folder_set:
    st.sidebar.info(f"Output directory: {OUTPUT_DATA_DIR}")
else:
    st.sidebar.warning("Output folder not set")

st.sidebar.markdown("---")

workflow_steps = [
    {"name": "1. Load Files & Filter Data", "completed": st.session_state.files_loaded},
    {"name": "2. Process Filtered Data", "completed": st.session_state.files_processed},
    {"name": "3. Generate/Load POA Matrix", "completed": st.session_state.poa_matrix_ready},
    {"name": "4. Run Evaluation", "completed": st.session_state.evaluation_completed},
    {"name": "5. Publish Results", "completed": st.session_state.publish_completed}
]
for i, step in enumerate(workflow_steps):
    step_num = i + 1
    if step["completed"]:
        status_class = "step-completed"
        icon = "✅"
    elif step_num == st.session_state.workflow_step:
        status_class = "step-current"
        icon = "🔄"
    else:
        status_class = "step-pending"
        icon = "⏳"
    if step["completed"] or step_num == st.session_state.workflow_step:
        if st.sidebar.button(f'{icon} {step["name"]}', key=f"nav_step_{step_num}", help=f"Navigate to {step['name']}"):
            st.session_state.workflow_step = step_num
            st.rerun()
    else:
        st.sidebar.markdown(f'<div class="workflow-step {status_class}">{icon} {step["name"]}</div>', unsafe_allow_html=True)

st.sidebar.markdown("---")

st.session_state.show_logs = st.sidebar.checkbox("📝 Show Processing Logs", value=st.session_state.show_logs)

# Additional sidebar sections and main workflow follow here (unchanged)
