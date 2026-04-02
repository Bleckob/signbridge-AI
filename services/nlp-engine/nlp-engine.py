import json
import asyncio
import os
from rapidfuzz import process, fuzz
from dotenv import load_dotenv
from pathlib import Path
import redis.asyncio as aioredis

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

redis_client = aioredis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    username=os.getenv("REDIS_USERNAME", "default"),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
    ssl=False,
)

# General-purpose lexicon — covers everyday life, education, social settings,
# transport, work, and medical contexts (Nigerian hospitals included).
# Each entry: (phrase, [SIGN_IDs], duration_ms, NMM_tags)
# Each phrase maps DIRECTLY to ordered pose sequence + NMM tags
# TODO (Task 05): Replace mock with Supabase query to sign_poses table
LEXICON = [

    # ── Core Responses ────────────────────────────────────────────────────────
    ("yes",                           ["SIGN_YES"],                                          500,  {"head_nod": 0.9}),
    ("no",                            ["SIGN_NO"],                                           500,  {"head_shake": 0.9}),
    ("please",                        ["SIGN_PLEASE"],                                       600,  {"head_tilt": 0.1}),
    ("thank you",                     ["SIGN_THANK", "SIGN_YOU"],                            800,  {"head_nod": 0.8}),
    ("you are welcome",               ["SIGN_YOU", "SIGN_WELCOME"],                          900,  {"smile": 0.7}),
    ("sorry",                         ["SIGN_SORRY"],                                        700,  {"eyebrows_furrow": 0.3}),
    ("excuse me",                     ["SIGN_EXCUSE", "SIGN_ME"],                            800,  {"head_tilt": 0.2}),
    ("i understand",                  ["SIGN_I", "SIGN_UNDERSTAND"],                         900,  {"head_nod": 0.6}),
    ("i do not understand",           ["SIGN_I", "SIGN_NOT", "SIGN_UNDERSTAND"],             1100, {"head_shake": 0.5, "eyebrows_furrow": 0.4}),
    ("do you understand",             ["SIGN_DO", "SIGN_YOU", "SIGN_UNDERSTAND"],            1100, {"eyebrows_raise": 0.5}),
    ("repeat please",                 ["SIGN_REPEAT", "SIGN_PLEASE"],                        900,  {"eyebrows_raise": 0.4}),
    ("slow down please",              ["SIGN_SLOW", "SIGN_DOWN", "SIGN_PLEASE"],             1000, {"eyebrows_raise": 0.3}),
    ("i agree",                       ["SIGN_I", "SIGN_AGREE"],                              800,  {"head_nod": 0.7}),
    ("i disagree",                    ["SIGN_I", "SIGN_DISAGREE"],                           900,  {"head_shake": 0.6}),
    ("maybe",                         ["SIGN_MAYBE"],                                        700,  {"head_tilt": 0.4}),
    ("i do not know",                 ["SIGN_I", "SIGN_NOT", "SIGN_KNOW"],                   900,  {"eyebrows_raise": 0.5, "head_shake": 0.3}),
    ("help me",                       ["SIGN_HELP", "SIGN_ME"],                              700,  {"eyebrows_furrow": 0.6}),
    ("wait",                          ["SIGN_WAIT"],                                         600,  {}),
    ("stop",                          ["SIGN_STOP"],                                         500,  {"eyebrows_furrow": 0.5}),
    ("finished",                      ["SIGN_FINISHED"],                                     600,  {}),

    # ── Greetings & Farewells ─────────────────────────────────────────────────
    ("hello",                         ["SIGN_HELLO"],                                        700,  {"smile": 0.8}),
    ("hi",                            ["SIGN_HI"],                                           500,  {"smile": 0.8}),
    ("good morning",                  ["SIGN_GOOD", "SIGN_MORNING"],                         1300, {"smile": 0.9}),
    ("good afternoon",                ["SIGN_GOOD", "SIGN_AFTERNOON"],                       1300, {"smile": 0.9}),
    ("good evening",                  ["SIGN_GOOD", "SIGN_EVENING"],                         1300, {"smile": 0.9}),
    ("good night",                    ["SIGN_GOOD", "SIGN_NIGHT"],                           1200, {"smile": 0.7}),
    ("welcome",                       ["SIGN_WELCOME"],                                      800,  {"smile": 0.8, "head_nod": 0.5}),
    ("goodbye",                       ["SIGN_GOODBYE"],                                      800,  {"smile": 0.6}),
    ("see you later",                 ["SIGN_SEE", "SIGN_YOU", "SIGN_LATER"],                1000, {"smile": 0.6}),
    ("see you tomorrow",              ["SIGN_SEE", "SIGN_YOU", "SIGN_TOMORROW"],             1100, {"smile": 0.6}),
    ("take care",                     ["SIGN_TAKE", "SIGN_CARE"],                            900,  {"smile": 0.5}),
    ("have a good day",               ["SIGN_HAVE", "SIGN_GOOD", "SIGN_DAY"],               1200, {"smile": 0.8}),

    # ── Identity & Personal Information ───────────────────────────────────────
    ("what is your name",             ["SIGN_WHAT", "SIGN_YOUR", "SIGN_NAME"],               1400, {"head_tilt": 0.2, "eyebrows_raise": 0.4}),
    ("my name is",                    ["SIGN_MY", "SIGN_NAME", "SIGN_IS"],                   1200, {}),
    ("how old are you",               ["SIGN_HOW", "SIGN_OLD", "SIGN_YOU"],                  1300, {"eyebrows_raise": 0.4}),
    ("where are you from",            ["SIGN_WHERE", "SIGN_YOU", "SIGN_FROM"],               1400, {"eyebrows_raise": 0.4}),
    ("where do you live",             ["SIGN_WHERE", "SIGN_YOU", "SIGN_LIVE"],               1400, {"eyebrows_raise": 0.4}),
    ("what is your address",          ["SIGN_WHAT", "SIGN_YOUR", "SIGN_ADDRESS"],            1500, {"eyebrows_raise": 0.3}),
    ("what is your phone number",     ["SIGN_WHAT", "SIGN_YOUR", "SIGN_PHONE", "SIGN_NUMBER"], 1700, {"eyebrows_raise": 0.3}),
    ("are you married",               ["SIGN_ARE", "SIGN_YOU", "SIGN_MARRIED"],              1200, {"eyebrows_raise": 0.4}),
    ("do you have children",          ["SIGN_DO", "SIGN_YOU", "SIGN_CHILDREN"],              1300, {"eyebrows_raise": 0.4}),

    # ── How Are You ───────────────────────────────────────────────────────────
    ("how are you",                   ["SIGN_HOW", "SIGN_FEEL", "SIGN_YOU"],                 1200, {"eyebrows_raise": 0.6}),
    ("i am fine",                     ["SIGN_I", "SIGN_FINE"],                               800,  {"smile": 0.7}),
    ("i am not fine",                 ["SIGN_I", "SIGN_NOT", "SIGN_FINE"],                   1000, {"eyebrows_furrow": 0.4}),
    ("i am tired",                    ["SIGN_I", "SIGN_TIRED"],                              900,  {"eyebrows_furrow": 0.3}),
    ("i am happy",                    ["SIGN_I", "SIGN_HAPPY"],                              800,  {"smile": 0.9}),
    ("i am sad",                      ["SIGN_I", "SIGN_SAD"],                                800,  {"eyebrows_furrow": 0.5}),
    ("i am hungry",                   ["SIGN_I", "SIGN_HUNGRY"],                             800,  {}),
    ("i am thirsty",                  ["SIGN_I", "SIGN_THIRSTY"],                            800,  {}),
    ("i am cold",                     ["SIGN_I", "SIGN_COLD"],                               700,  {}),
    ("i am hot",                      ["SIGN_I", "SIGN_HOT"],                                700,  {}),
    ("i am scared",                   ["SIGN_I", "SIGN_SCARED"],                             800,  {"eyebrows_raise": 0.6}),
    ("i am bored",                    ["SIGN_I", "SIGN_BORED"],                              800,  {}),
    ("i am busy",                     ["SIGN_I", "SIGN_BUSY"],                               800,  {}),

    # ── Questions ─────────────────────────────────────────────────────────────
    ("what is that",                  ["SIGN_WHAT", "SIGN_THAT"],                            900,  {"eyebrows_raise": 0.5}),
    ("what happened",                 ["SIGN_WHAT", "SIGN_HAPPEN"],                          1000, {"eyebrows_raise": 0.5}),
    ("what time is it",               ["SIGN_WHAT", "SIGN_TIME"],                            1000, {"eyebrows_raise": 0.4}),
    ("what day is today",             ["SIGN_WHAT", "SIGN_DAY", "SIGN_TODAY"],               1300, {"eyebrows_raise": 0.4}),
    ("when",                          ["SIGN_WHEN"],                                         600,  {"eyebrows_raise": 0.5}),
    ("where",                         ["SIGN_WHERE"],                                        600,  {"eyebrows_raise": 0.5}),
    ("who",                           ["SIGN_WHO"],                                          600,  {"eyebrows_raise": 0.5}),
    ("why",                           ["SIGN_WHY"],                                          600,  {"eyebrows_raise": 0.5}),
    ("how",                           ["SIGN_HOW"],                                          600,  {"eyebrows_raise": 0.5}),
    ("how much does it cost",         ["SIGN_HOW", "SIGN_MUCH", "SIGN_COST"],                1400, {"eyebrows_raise": 0.4}),
    ("how long will it take",         ["SIGN_HOW", "SIGN_LONG", "SIGN_TIME"],                1400, {"eyebrows_raise": 0.4}),
    ("can you help me",               ["SIGN_CAN", "SIGN_YOU", "SIGN_HELP", "SIGN_ME"],      1300, {"eyebrows_raise": 0.5}),
    ("can you show me",               ["SIGN_CAN", "SIGN_YOU", "SIGN_SHOW", "SIGN_ME"],      1300, {"eyebrows_raise": 0.4}),

    # ── Daily Life & Home ─────────────────────────────────────────────────────
    ("wake up",                       ["SIGN_WAKE", "SIGN_UP"],                              800,  {}),
    ("go to sleep",                   ["SIGN_GO", "SIGN_SLEEP"],                             900,  {}),
    ("eat food",                      ["SIGN_EAT", "SIGN_FOOD"],                             800,  {}),
    ("drink water",                   ["SIGN_DRINK", "SIGN_WATER"],                          800,  {}),
    ("cook food",                     ["SIGN_COOK", "SIGN_FOOD"],                            900,  {}),
    ("wash your hands",               ["SIGN_WASH", "SIGN_HANDS"],                           900,  {}),
    ("take a bath",                   ["SIGN_BATH"],                                         800,  {}),
    ("clean the house",               ["SIGN_CLEAN", "SIGN_HOUSE"],                          1000, {}),
    ("open the door",                 ["SIGN_OPEN", "SIGN_DOOR"],                            800,  {}),
    ("close the door",                ["SIGN_CLOSE", "SIGN_DOOR"],                           800,  {}),
    ("turn on the light",             ["SIGN_ON", "SIGN_LIGHT"],                             900,  {}),
    ("turn off the light",            ["SIGN_OFF", "SIGN_LIGHT"],                            900,  {}),
    ("go outside",                    ["SIGN_GO", "SIGN_OUTSIDE"],                           800,  {}),
    ("come inside",                   ["SIGN_COME", "SIGN_INSIDE"],                          800,  {}),
    ("sit down",                      ["SIGN_SIT", "SIGN_DOWN"],                             700,  {}),
    ("stand up",                      ["SIGN_STAND", "SIGN_UP"],                             800,  {}),

    # ── Education & School ────────────────────────────────────────────────────
    ("i am a student",                ["SIGN_I", "SIGN_AM", "SIGN_STUDENT"],                 1200, {}),
    ("i am a teacher",                ["SIGN_I", "SIGN_AM", "SIGN_TEACHER"],                 1200, {}),
    ("go to school",                  ["SIGN_GO", "SIGN_SCHOOL"],                            900,  {}),
    ("do your homework",              ["SIGN_DO", "SIGN_YOUR", "SIGN_HOMEWORK"],             1200, {}),
    ("open your book",                ["SIGN_OPEN", "SIGN_BOOK"],                            800,  {}),
    ("write it down",                 ["SIGN_WRITE", "SIGN_DOWN"],                           900,  {}),
    ("read this",                     ["SIGN_READ", "SIGN_THIS"],                            800,  {}),
    ("pay attention",                 ["SIGN_PAY", "SIGN_ATTENTION"],                        1000, {"eyebrows_raise": 0.3}),
    ("class is over",                 ["SIGN_CLASS", "SIGN_OVER"],                           900,  {}),
    ("i passed my exam",              ["SIGN_I", "SIGN_PASS", "SIGN_EXAM"],                  1300, {"smile": 0.8}),
    ("i failed my exam",              ["SIGN_I", "SIGN_FAIL", "SIGN_EXAM"],                  1300, {"eyebrows_furrow": 0.5}),

    # ── Work & Professional ───────────────────────────────────────────────────
    ("i am working",                  ["SIGN_I", "SIGN_WORK"],                               900,  {}),
    ("i need a job",                  ["SIGN_I", "SIGN_NEED", "SIGN_JOB"],                   1100, {}),
    ("i got the job",                 ["SIGN_I", "SIGN_GET", "SIGN_JOB"],                    1100, {"smile": 0.8}),
    ("meeting at what time",          ["SIGN_MEETING", "SIGN_WHAT", "SIGN_TIME"],            1400, {"eyebrows_raise": 0.4}),
    ("the meeting is cancelled",      ["SIGN_MEETING", "SIGN_CANCEL"],                       1200, {}),
    ("i am late",                     ["SIGN_I", "SIGN_LATE"],                               800,  {"eyebrows_furrow": 0.4}),
    ("deadline is tomorrow",          ["SIGN_DEADLINE", "SIGN_TOMORROW"],                    1200, {}),
    ("sign this document",            ["SIGN_SIGN", "SIGN_DOCUMENT"],                        1000, {}),
    ("send me the report",            ["SIGN_SEND", "SIGN_ME", "SIGN_REPORT"],               1200, {}),

    # ── Transport & Directions ────────────────────────────────────────────────
    ("where is the bus stop",         ["SIGN_WHERE", "SIGN_BUS", "SIGN_STOP"],               1500, {"eyebrows_raise": 0.4}),
    ("how do i get to",               ["SIGN_HOW", "SIGN_GET", "SIGN_TO"],                   1300, {"eyebrows_raise": 0.4}),
    ("turn left",                     ["SIGN_TURN", "SIGN_LEFT"],                            800,  {}),
    ("turn right",                    ["SIGN_TURN", "SIGN_RIGHT"],                           800,  {}),
    ("go straight",                   ["SIGN_GO", "SIGN_STRAIGHT"],                          800,  {}),
    ("it is far",                     ["SIGN_IT", "SIGN_FAR"],                               800,  {}),
    ("it is nearby",                  ["SIGN_IT", "SIGN_NEAR"],                              800,  {}),
    ("i am lost",                     ["SIGN_I", "SIGN_LOST"],                               900,  {"eyebrows_furrow": 0.5}),
    ("i missed the bus",              ["SIGN_I", "SIGN_MISS", "SIGN_BUS"],                   1100, {"eyebrows_furrow": 0.4}),
    ("stop here",                     ["SIGN_STOP", "SIGN_HERE"],                            800,  {}),
    ("i am going home",               ["SIGN_I", "SIGN_GO", "SIGN_HOME"],                    1000, {}),

    # ── Shopping & Money ──────────────────────────────────────────────────────
    ("how much is this",              ["SIGN_HOW", "SIGN_MUCH", "SIGN_THIS"],                1200, {"eyebrows_raise": 0.4}),
    ("i want to buy this",            ["SIGN_I", "SIGN_WANT", "SIGN_BUY", "SIGN_THIS"],      1500, {}),
    ("this is too expensive",         ["SIGN_THIS", "SIGN_TOO", "SIGN_EXPENSIVE"],           1300, {"eyebrows_furrow": 0.4}),
    ("do you have change",            ["SIGN_YOU", "SIGN_HAVE", "SIGN_CHANGE"],              1200, {"eyebrows_raise": 0.4}),
    ("i do not have money",           ["SIGN_I", "SIGN_NO", "SIGN_MONEY"],                   1100, {}),
    ("pay with card",                 ["SIGN_PAY", "SIGN_CARD"],                             900,  {}),
    ("give me a discount",            ["SIGN_GIVE", "SIGN_ME", "SIGN_DISCOUNT"],             1200, {}),
    ("i want a refund",               ["SIGN_I", "SIGN_WANT", "SIGN_REFUND"],                1100, {}),

    # ── Emergency & Safety ────────────────────────────────────────────────────
    ("this is an emergency",          ["SIGN_EMERGENCY"],                                    800,  {"eyebrows_furrow": 0.9}),
    ("call the police",               ["SIGN_CALL", "SIGN_POLICE"],                          1000, {"eyebrows_furrow": 0.8}),
    ("call an ambulance",             ["SIGN_CALL", "SIGN_AMBULANCE"],                       1000, {"eyebrows_furrow": 0.8}),
    ("there is a fire",               ["SIGN_FIRE", "SIGN_THERE"],                           1000, {"eyebrows_furrow": 0.9}),
    ("i have been robbed",            ["SIGN_I", "SIGN_ROBBED"],                             1100, {"eyebrows_furrow": 0.8}),
    ("stay calm",                     ["SIGN_STAY", "SIGN_CALM"],                            900,  {"eyebrows_raise": 0.3}),
    ("do not panic",                  ["SIGN_DO_NOT", "SIGN_PANIC"],                         1000, {"eyebrows_raise": 0.4}),
    ("you are safe",                  ["SIGN_YOU", "SIGN_SAFE"],                             900,  {"smile": 0.5, "head_nod": 0.4}),
    ("evacuate now",                  ["SIGN_EVACUATE", "SIGN_NOW"],                         900,  {"eyebrows_furrow": 0.7}),

    # ── Medical & Health ──────────────────────────────────────────────────────
    ("i am a doctor",                 ["SIGN_I", "SIGN_AM", "SIGN_DOCTOR"],                  1400, {}),
    ("i am a nurse",                  ["SIGN_I", "SIGN_AM", "SIGN_NURSE"],                   1400, {}),
    ("where does it hurt",            ["SIGN_WHERE", "SIGN_PAIN", "SIGN_LOCATION"],          1800, {"eyebrows_furrow": 0.5}),
    ("are you in pain",               ["SIGN_ARE", "SIGN_YOU", "SIGN_PAIN"],                 1500, {"eyebrows_furrow": 0.4}),
    ("open your mouth",               ["SIGN_OPEN", "SIGN_MOUTH"],                           900,  {"mouth_open": 0.8}),
    ("breathe deeply",                ["SIGN_BREATHE", "SIGN_DEEP"],                         1200, {"chest_expand": 0.7}),
    ("take this medicine",            ["SIGN_TAKE", "SIGN_MEDICINE"],                        1500, {}),
    ("twice a day",                   ["SIGN_TWICE", "SIGN_DAY"],                            1100, {}),
    ("do you have a fever",           ["SIGN_FEVER", "SIGN_YOU"],                            1200, {"eyebrows_furrow": 0.4}),
    ("lie down",                      ["SIGN_LIE", "SIGN_DOWN"],                             900,  {}),
    ("relax",                         ["SIGN_RELAX"],                                        700,  {"smile": 0.5}),
    ("you will be fine",              ["SIGN_YOU", "SIGN_FINE", "SIGN_FUTURE"],              1200, {"smile": 0.7, "head_nod": 0.5}),
    ("call a doctor",                 ["SIGN_CALL", "SIGN_DOCTOR"],                          1000, {"eyebrows_furrow": 0.7}),
    ("i need a blood sample",         ["SIGN_NEED", "SIGN_BLOOD", "SIGN_SAMPLE"],            1600, {"eyebrows_raise": 0.3}),
    ("are you on any medication",     ["SIGN_YOU", "SIGN_MEDICINE", "SIGN_NOW"],             1500, {"eyebrows_raise": 0.4}),
    ("you need to be admitted",       ["SIGN_YOU", "SIGN_ADMIT", "SIGN_HOSPITAL"],           1600, {}),
    ("you can go home",               ["SIGN_YOU", "SIGN_GO", "SIGN_HOME"],                  1200, {"smile": 0.7}),

    # ── Technology & Communication ────────────────────────────────────────────
    ("send me a message",             ["SIGN_SEND", "SIGN_ME", "SIGN_MESSAGE"],              1200, {}),
    ("call me",                       ["SIGN_CALL", "SIGN_ME"],                              800,  {}),
    ("my phone is dead",              ["SIGN_MY", "SIGN_PHONE", "SIGN_DEAD"],                1100, {}),
    ("the internet is not working",   ["SIGN_INTERNET", "SIGN_NOT", "SIGN_WORK"],            1400, {"eyebrows_furrow": 0.4}),
    ("what is the password",          ["SIGN_WHAT", "SIGN_PASSWORD"],                        1100, {"eyebrows_raise": 0.3}),
    ("take a picture",                ["SIGN_TAKE", "SIGN_PICTURE"],                         900,  {}),
    ("turn on the phone",             ["SIGN_PHONE", "SIGN_ON"],                             800,  {}),
    ("i am online",                   ["SIGN_I", "SIGN_ONLINE"],                             800,  {}),

    # ── Time & Planning ───────────────────────────────────────────────────────
    ("i am running late",             ["SIGN_I", "SIGN_LATE", "SIGN_RUN"],                   1100, {"eyebrows_furrow": 0.4}),
    ("i am free on monday",           ["SIGN_I", "SIGN_FREE", "SIGN_MONDAY"],                1300, {}),
    ("lets meet at noon",             ["SIGN_MEET", "SIGN_NOON"],                            1100, {}),
    ("the event is next week",        ["SIGN_EVENT", "SIGN_NEXT", "SIGN_WEEK"],              1400, {}),
    ("i will be back soon",           ["SIGN_I", "SIGN_BACK", "SIGN_SOON"],                  1100, {}),

    # ── Feelings & Social ─────────────────────────────────────────────────────
    ("i love you",                    ["SIGN_I", "SIGN_LOVE", "SIGN_YOU"],                   1000, {"smile": 0.9}),
    ("i miss you",                    ["SIGN_I", "SIGN_MISS", "SIGN_YOU"],                   1000, {"smile": 0.6}),
    ("happy birthday",                ["SIGN_HAPPY", "SIGN_BIRTHDAY"],                       1100, {"smile": 0.9}),
    ("congratulations",               ["SIGN_CONGRATULATIONS"],                              900,  {"smile": 0.9, "head_nod": 0.6}),
    ("good luck",                     ["SIGN_GOOD", "SIGN_LUCK"],                            900,  {"smile": 0.7}),
    ("i am proud of you",             ["SIGN_I", "SIGN_PROUD", "SIGN_YOU"],                  1200, {"smile": 0.8}),
    ("well done",                     ["SIGN_WELL", "SIGN_DONE"],                            800,  {"smile": 0.8, "head_nod": 0.6}),
    ("that is funny",                 ["SIGN_THAT", "SIGN_FUNNY"],                           900,  {"smile": 0.8}),
    ("i am angry",                    ["SIGN_I", "SIGN_ANGRY"],                              800,  {"eyebrows_furrow": 0.7}),
    ("calm down",                     ["SIGN_CALM", "SIGN_DOWN"],                            900,  {"eyebrows_raise": 0.3}),

    # Add more as Isaac syncs 300-sign DB (weekly)
]

# Keep backward-compatible alias so any code still referencing MEDICAL_LEXICON keeps working
MEDICAL_LEXICON = LEXICON

def normalize_text(text: str) -> str:
    return text.lower().strip()

async def text_to_sign_poses(text: str, session_id: str) -> dict:
    """DIRECT speech → pose lookup (no gloss)"""
    if not text:
        return {"poses": [], "session_id": session_id}

    normalized = normalize_text(text)
    
    # Fuzzy best-match per phrase (real-time)
    matches = []
    for phrase, pose_ids, duration, nmm in LEXICON:
        score = process.extractOne(normalized, [phrase], scorer=fuzz.partial_ratio)
        if score and score[1] >= 75:  # 75% confidence threshold
            matches.append((pose_ids, duration, nmm, score[1]))

    # Sort by confidence & build ordered sequence
    matches.sort(key=lambda x: -x[3])
    
    pose_sequence = []
    total_duration = 0
    for pose_ids, dur, nmm, _ in matches:
        for pid in pose_ids:
            pose_sequence.append({
                "sign_id": pid,                    # Isaac's DB key (Task 05)
                "duration_ms": dur // len(pose_ids),
                "nmm": nmm,                        # Non-manual markers for avatar
                "keyframes": []                    # Placeholder – Isaac fills real MediaPipe quaternions
            })
        total_duration += dur

    result = {
        "type": "nlp_output",
        "session_id": session_id,
        "text": text,
        "poses": pose_sequence,
        "total_duration_ms": total_duration or 800,
        "nmm_global": {"speed": 1.0},              # Global avatar settings
        # BUG FIX: get_event_loop() is deprecated in Python 3.10+;
        # use get_running_loop() inside async context instead.
        "timestamp": asyncio.get_running_loop().time()
    }

    # Publish to next stage (avatar animation); session_id is in the payload.
    await redis_client.xadd(
        "nlp-output",
        {"data": json.dumps(result)},
        maxlen=500,
        approximate=True
    )

    print(f"NLP (direct) → {len(pose_sequence)} poses | '{text[:60]}...' → {total_duration} ms")
    return result

# Redis consumer (runs in background)
async def nlp_redis_consumer():
    """Listens to asr-output → produces nlp-output"""
    # BUG FIX: Redis XREAD does not support wildcard patterns.
    # Use a fixed stream name; session_id is carried inside the message payload.
    stream_key = "asr-output"
    last_id = "$"

    while True:
        try:
            messages = await redis_client.xread(
                {stream_key: last_id},
                count=10,
                block=100
            )
            for stream, msgs in messages or []:
                for msg_id, data in msgs or []:
                    try:
                        payload = json.loads(data["data"])
                        if payload.get("type") == "asr_output" and payload.get("text"):
                            await text_to_sign_poses(payload["text"], payload["session_id"])
                        # Advance cursor only after successful processing to avoid
                        # silently skipping failed messages.
                        last_id = msg_id
                    except Exception as e:
                        print(f"NLP parse error: {e}")
        except Exception as e:
            print(f"NLP Redis error: {e}")
            await asyncio.sleep(0.1)  # back-off only on error; block=100 handles idle
