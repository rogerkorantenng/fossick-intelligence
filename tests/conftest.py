import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("SLACK_WEBHOOK_URL", "")
os.environ.setdefault("SLACK_SIGNING_SECRET", "")
