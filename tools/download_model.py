"""Fetch the Turbo model into this utility's local Hugging Face cache."""
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.environ['HF_HOME'] = str(root / 'models')
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id='ResembleAI/chatterbox-turbo',
    allow_patterns=['*.safetensors', '*.json', '*.txt', '*.pt', '*.model'],
)
print('Turbo model ready in', root / 'models')
