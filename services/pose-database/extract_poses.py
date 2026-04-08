# Extract poses from a video and save them to a supabase database.
# takes a video file, runs MediaPipe Holistic, converts landmarks to quaternion
# keyframes, and inserts a row into sign_poses.
# video -> mediapipe -> supabase

# remember to import bone_names.py

