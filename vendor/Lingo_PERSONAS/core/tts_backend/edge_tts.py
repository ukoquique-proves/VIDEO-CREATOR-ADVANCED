from pathlib import Path
import edge_tts as edge_tts_module
import asyncio
from core.utils import load_key

# Available voices can be listed using edge-tts --list-voices command
# Common English voices:
# en-US-JennyNeural - Female
# en-US-GuyNeural - Male  
# en-GB-SoniaNeural - Female British
# Common Chinese voices:
# zh-CN-XiaoxiaoNeural - Female
# zh-CN-YunxiNeural - Male
# zh-CN-XiaoyiNeural - Female

async def edge_tts_async(text, save_path, voice):
    """Async function to generate TTS using edge-tts Python API."""
    communicate = edge_tts_module.Communicate(text, voice)
    await communicate.save(save_path)

def edge_tts(text, save_path):
    """Generate TTS using edge-tts Python API (synchronous wrapper)."""
    # Load settings from config file
    edge_set = load_key("edge_tts")
    voice = edge_set.get("voice", "en-US-JennyNeural")
    
    # Create output directory if it doesn't exist
    speech_file_path = Path(save_path)
    speech_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Run async function
    asyncio.run(edge_tts_async(text, str(speech_file_path), voice))
    print(f"Audio saved to {speech_file_path}")

if __name__ == "__main__":
    edge_tts("Today is a good day!", "edge_tts.wav")
