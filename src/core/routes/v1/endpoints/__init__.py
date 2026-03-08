from .chat import create_chat_bp
from .health import create_health_bp
from .nlu import create_nlu_bp
from .plan import create_plan_bp
from .record import create_record_bp

__all__ = [
    "create_chat_bp",
    "create_health_bp",
    "create_nlu_bp",
    "create_plan_bp",
    "create_record_bp",
]
