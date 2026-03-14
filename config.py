"""
Reproducibility-focused configuration for offline EduBench experiments.
"""
import os
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_secret_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _models_url_from_completions(url: str) -> str:
    return url.replace("/v1/completions", "/v1/models")


PROJECT_ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = PROJECT_ROOT.parent

DOCS_DIR = PROJECT_ROOT / "docs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

OUTPUT_ROOT = PROJECT_ROOT / "outputs"
LEGACY_OUTPUT_RESULTS_DIR = OUTPUT_ROOT / "results"
OUTPUT_PREDICTION_DIR = OUTPUT_ROOT / "predictions"
OUTPUT_SUMMARY_DIR = OUTPUT_ROOT / "summaries"
OUTPUT_TRACE_DIR = OUTPUT_ROOT / "traces"
OUTPUT_EVAL_CACHE_DIR = OUTPUT_ROOT / "eval_cache"

RUNTIME_DIR = PROJECT_ROOT / "runtime"
RUNTIME_DB_DIR = RUNTIME_DIR / "db"
RUNTIME_LOG_DIR = RUNTIME_DIR / "logs"
RUNTIME_SECRET_DIR = RUNTIME_DIR / "secrets"
LEGACY_SECRET_FILE = PROJECT_ROOT / "GPT-key"

for path in (
    LEGACY_OUTPUT_RESULTS_DIR,
    OUTPUT_PREDICTION_DIR,
    OUTPUT_SUMMARY_DIR,
    OUTPUT_TRACE_DIR,
    OUTPUT_EVAL_CACHE_DIR,
    RUNTIME_DB_DIR,
    RUNTIME_LOG_DIR,
    RUNTIME_SECRET_DIR,
):
    path.mkdir(parents=True, exist_ok=True)


# Model configuration
MODEL_PATH_1B = os.getenv(
    "MODEL_PATH_1B",
    str(WORKSPACE_ROOT / "openPangu-Embedded-1B-V1.1"),
)
MODEL_PATH_7B = os.getenv(
    "MODEL_PATH_7B",
    str(WORKSPACE_ROOT / "openPangu-Embedded-7B-V1.1"),
)
MODEL_NAME_1B = os.getenv("MODEL_NAME_1B", "pangu_embedded_1b")
MODEL_NAME_7B = os.getenv("MODEL_NAME_7B", "pangu_embedded_7b")

VLLM_API_URL_1B = os.getenv("VLLM_API_URL_1B", "http://172.17.0.1:1040/v1/completions")
VLLM_API_URL_7B = os.getenv("VLLM_API_URL_7B", "http://172.17.0.1:8000/v1/completions")
VLLM_MODELS_URL_1B = _models_url_from_completions(VLLM_API_URL_1B)
VLLM_MODELS_URL_7B = _models_url_from_completions(VLLM_API_URL_7B)

# Backward-compatible aliases
MODEL_PATH = MODEL_PATH_7B
MODEL_NAME = MODEL_NAME_7B
VLLM_API_URL = VLLM_API_URL_7B
VLLM_MODELS_URL = VLLM_MODELS_URL_7B


# GPT judge configuration
GPT5_API_KEY_FILE = Path(
    os.getenv("GPT5_API_KEY_FILE", str(RUNTIME_SECRET_DIR / "GPT-key"))
)
GPT5_API_KEY = (
    os.getenv("GPT5_API_KEY")
    or _read_secret_file(GPT5_API_KEY_FILE)
    or _read_secret_file(LEGACY_SECRET_FILE)
)
GPT5_API_BASE = os.getenv("GPT5_API_BASE", "https://api.aicodemirror.com/v1")
GPT5_MODEL_NAME = os.getenv("GPT5_MODEL_NAME", "gpt-5.4")


# Dataset configuration
DATA_DIR = str(WORKSPACE_ROOT / "EduBench" / "data" / "all_data")
ZH_DATA_DIR = os.path.join(DATA_DIR, "zh_data")
EN_DATA_DIR = os.path.join(DATA_DIR, "en_data")

PRIMARY_TASK_KEYS = ["Q&A", "AG", "EC", "IP", "PCC", "PLS", "QG", "TMG"]
SUPPLEMENTARY_TASK_KEYS = ["ES"]

TASK_TYPES = {
    "Q&A": "question_answering",
    "AG": "automatic_grading",
    "EC": "error_correction",
    "IP": "idea_prompting",
    "PCC": "personalized_content",
    "PLS": "personalized_learning",
    "QG": "question_generation",
    "TMG": "teaching_material",
    "ES": "emotional_support",
}


# Reproducibility configuration
DEV_RATIO = 0.1
RANDOM_SEED = 42
DEBUG_MODE = False
ENABLE_DEBUG_SAMPLING = _env_bool("PANGU_DEBUG_SAMPLING", False)
DEBUG_SAMPLE_SIZE = int(os.getenv("PANGU_DEBUG_SAMPLE_SIZE", "32"))


# Inference configuration
MAX_NEW_TOKENS_FAST = 512
MAX_NEW_TOKENS_SLOW = 2048
MAX_NEW_TOKENS_SELF_EVAL = 200
TEMPERATURE_FAST = 0.2
TEMPERATURE_SLOW = 0.4
TEMPERATURE_SELF_EVAL = 0.0
TOP_P = 0.9
DEFAULT_EXPLANATION_LEVEL = "detailed"


# Baseline router heuristics
DIFFICULTY_KEYWORDS = {
    "easy": ["小学", "基础", "简单", "初级", "elementary", "basic", "simple", "primary"],
    "medium": ["中学", "中等", "初中", "middle", "intermediate", "secondary"],
    "hard": [
        "高中",
        "高级",
        "困难",
        "复杂",
        "大学",
        "高等",
        "high school",
        "advanced",
        "complex",
        "university",
    ],
}

SUBJECT_KEYWORDS = {
    "math": ["数学", "数", "计算", "方程", "几何", "math", "calculate", "equation", "geometry"],
    "physics": ["物理", "力学", "电学", "physics", "mechanics", "electricity"],
    "chemistry": ["化学", "元素", "反应", "chemistry", "element", "reaction"],
    "chinese": ["语文", "汉语", "文言文", "作文", "chinese", "writing", "literature"],
    "english": ["英语", "英文", "english", "grammar"],
    "other": [],
}


# API/service configuration kept for compatibility, but offline experiments are primary.
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8080"))
API_PREFIX = "/api/v1"
CORS_ORIGINS = ["*"]

BASE_DIR = str(PROJECT_ROOT)
DATABASE_FILE = Path(os.getenv("DATABASE_FILE", str(RUNTIME_DB_DIR / "agentv2.db")))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DATABASE_FILE}")
DATABASE_ECHO = False

SESSION_EXPIRE_HOURS = 24
SESSION_MAX_MESSAGES = 100
SESSION_TITLE_MAX_LENGTH = 50

MEMORY_MAX_MESSAGES = 20
MEMORY_MAX_TOKENS = 4096
MEMORY_COMPRESSION_THRESHOLD = 0.8

TOOL_TIMEOUT_SECONDS = 30
TOOL_MAX_RETRIES = 2
ENABLED_TOOLS = ["calculator", "knowledge", "formula_lookup"]

AGENT_MAX_TOOL_CALLS = 3
AGENT_TOOL_DETECTION_KEYWORDS = {
    "calculator": ["计算", "等于", "求", "算", "calculate", "compute", "="],
    "knowledge": ["什么是", "解释", "定义", "what is", "explain", "define"],
    "formula_lookup": ["公式", "定理", "formula", "theorem"],
}
