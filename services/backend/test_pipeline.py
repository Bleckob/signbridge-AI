import sys
import os
import json

# This line tells Python where to find your modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.redis_client import get_redis

def test_pipeline():
    redis = get_redis()
    
    # Simulate Amos dropping a message on nlp-output stream
    message_id = redis.xadd('nlp-output', {
        'session_id': 'test-session-001',
        'data': json.dumps({'gloss': 'HELLO DOCTOR MEDICINE'})
    })
    
    print(f"✅ Test message pushed to nlp-output")
    print(f"Message ID: {message_id}")

test_pipeline()