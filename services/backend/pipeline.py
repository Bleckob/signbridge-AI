import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from backend.redis_client import get_redis
from backend.supabase_client import get_sign_pose
from backend.animation import assemble_animation_package, parse_gloss_from_nlp
from backend.latency import StageTimer
from backend.websocket_manager import manager

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Stream names — same ones we defined in redis_streams.py
STREAM_NLP_OUTPUT = "nlp-output"
STREAM_SESSION_RESULT = "session-result"


async def process_nlp_output(message_id: str, session_id: str, nlp_data: str):
    """
    Processes a single NLP output message from Amos.
    This is the core of your pipeline.

    Steps:
    1. Parse gloss list from Amos's output
    2. Look up each pose from Supabase
    3. Assemble animation package
    4. Push to session-result stream
    5. Send to David's WebSocket

    message_id: Redis message ID
    session_id: which user this is for
    nlp_data: raw NLP output from Amos
    """

    # Start total pipeline timer
    total_timer = StageTimer("pipeline_total")
    total_timer.start()

    try:
        # =============================================
        # STAGE 1: Parse gloss list from Amos's output
        # =============================================
        print(f"Pipeline started for session: {session_id}")
        gloss_list = parse_gloss_from_nlp(nlp_data)

        if not gloss_list:
            print(f"No gloss found in NLP output: {nlp_data}")
            return

        print(f"Gloss list parsed: {gloss_list}")

        # =============================================
        # STAGE 2: Look up poses from Supabase
        # =============================================
        pose_timer = StageTimer("pose_lookup")
        pose_timer.start()

        pose_data_list = []
        for gloss in gloss_list:
            pose = get_sign_pose(gloss)
            pose_data_list.append(pose)
            print(f"Pose fetched for: {gloss}")

        pose_timer.stop()

        # =============================================
        # STAGE 3: Assemble animation package
        # =============================================
        animation_package = assemble_animation_package(
            session_id=session_id,
            gloss_list=gloss_list,
            pose_data_list=pose_data_list
        )

        print(f"Animation package assembled: {len(gloss_list)} signs")

        # =============================================
        # STAGE 4: Push to session-result Redis stream
        # So David can pick it up
        # =============================================
        redis = get_redis()
        redis.xadd(STREAM_SESSION_RESULT, {
            "session_id": session_id,
            "data": json.dumps(animation_package)
        })

        print("Animation pushed to session-result stream ✅")

        # =============================================
        # STAGE 5: Send directly to David via WebSocket
        # This is faster than waiting for David to read Redis
        # =============================================
        await manager.send_message(session_id, animation_package)
        print("Animation sent to David via WebSocket ✅")

    except Exception as e:
        print(f"Pipeline error for session {session_id}: {e}")

    finally:
        # Always stop total timer even if something went wrong
        total_duration = total_timer.stop()
        print(f"Pipeline completed in {total_duration:.2f}ms")

        # Warn if we're close to or over the 1500ms budget
        if total_duration > 1500:
            print("⚠️ WARNING: Pipeline exceeded 1500ms budget!")
        elif total_duration > 1200:
            print(f"⚠️ CAUTION: Pipeline at {total_duration:.2f}ms — close to budget")


async def run_pipeline_listener():
    # ... your existing docstring ...
    redis = get_redis()
    last_id = "$"

    # --- ADD THIS LINE HERE ---
    await asyncio.sleep(0.1)

    print("Pipeline listener started — waiting for NLP output... 👂")

    while True:
        # --- ADD THIS LINE HERE (indented once) ---
        await asyncio.sleep(0.01)

        try: # This 'try' must be lined up exactly under the 'await' above
            # ... all your existing Redis logic stays here ...
            messages = redis.xread(
                {STREAM_NLP_OUTPUT: last_id},
                count=10,
                block=1000
            )

            if messages:
                for stream_name, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        last_id = message_id
                        session_id = message_data.get("session_id", "unknown")
                        nlp_data = message_data.get("data", "")

                        print(f"New NLP message received: {message_id}")

                        await process_nlp_output(
                            message_id=message_id,
                            session_id=session_id,
                            nlp_data=nlp_data
                        )

        except Exception as e:
            print(f"Pipeline listener error: {e}")
            await asyncio.sleep(2)




# async def run_pipeline_listener():
#     """
#     Continuously listens to the nlp-output Redis stream.
#     When Amos drops something on the stream, this picks it up
#     and runs it through the pipeline.

#     This runs as a background task — it never stops until
#     the server shuts down.
#     """
#     redis = get_redis()
#     last_id = "$"  # $ means only read NEW messages from now on

#     print("Pipeline listener started — waiting for NLP output... 👂")

#     while True:
#         try:
#             # Read from nlp-output stream
#             # block=1000 means wait up to 1000ms for new messages
#             messages = redis.xread(
#                 {STREAM_NLP_OUTPUT: last_id},
#                 count=10,
#                 block=1000
#             )

#             if messages:
#                 # messages format: [(stream_name, [(message_id, data), ...])]
#                 for stream_name, stream_messages in messages:
#                     for message_id, message_data in stream_messages:
#                         # Update last_id so we don't re-process old messages
#                         last_id = message_id

#                         # Extract session_id and data from message
#                         session_id = message_data.get("session_id", "unknown")
#                         nlp_data = message_data.get("data", "")

#                         print(f"New NLP message received: {message_id}")

#                         # Process the message through the pipeline
#                         await process_nlp_output(
#                             message_id=message_id,
#                             session_id=session_id,
#                             nlp_data=nlp_data
#                         )

#         except Exception as e:
#             print(f"Pipeline listener error: {e}")
#             # Wait 2 seconds before retrying
#             # This prevents the loop from crashing the server
#             await asyncio.sleep(2)
