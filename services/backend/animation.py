import json
from typing import List, Dict
from datetime import datetime


def assemble_animation_package(
    session_id: str,
    gloss_list: List[str],
    pose_data_list: List[Dict]
) -> Dict:
    """
    Assembles the final animation package that David's avatar needs.
    
    session_id: which user this animation is for
    gloss_list: list of sign language words
                Example: ["HELLO", "DOCTOR", "MEDICINE"]
    pose_data_list: list of pose data fetched from Supabase
                    One pose per gloss word
    
    Returns a complete animation package ready to send to David.
    """

    # Build individual sign animations
    signs = []
    total_duration = 0

    for i, (gloss, pose_data) in enumerate(zip(gloss_list, pose_data_list)):
        duration = pose_data.get("duration_ms", 500)
        total_duration += duration

        sign = {
            "index": i,
            "gloss": gloss,
            "keyframes": pose_data.get("keyframes", []),
            "duration_ms": duration,
            "is_placeholder": pose_data.get("placeholder", False)
        }
        signs.append(sign)

    # Build the complete animation package
    animation_package = {
        "type": "animation_package",
        "session_id": session_id,
        "timestamp": datetime.utcnow().isoformat(),
        "total_signs": len(signs),
        "total_duration_ms": total_duration,
        "signs": signs,
        "metadata": {
            "assembled_at": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    }

    return animation_package


def parse_gloss_from_nlp(nlp_output: str) -> List[str]:
    """
    Parses the gloss list from Amos's NLP output.
    
    nlp_output: the raw string that Amos pushes to nlp-output stream
    
    Returns a list of gloss words.
    Example: "HELLO DOCTOR MEDICINE" → ["HELLO", "DOCTOR", "MEDICINE"]
    """
    try:
        # Try parsing as JSON first
        data = json.loads(nlp_output)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "gloss" in data:
            gloss_string = data["gloss"]
            return gloss_string.strip().upper().split()
    except json.JSONDecodeError:
        # If not JSON, treat as plain space-separated string
        return nlp_output.strip().upper().split()
    
    return []