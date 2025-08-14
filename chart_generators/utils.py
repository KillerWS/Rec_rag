from typing import Dict

def generate_error_response(error_message: str) -> Dict:
    return {
        "success": False,
        "error": error_message,
        "chart_config": None,
        "data": None,
        "echarts_option": None
    } 