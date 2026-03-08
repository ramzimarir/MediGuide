"""Voice Activity Detection using Silero VAD model via PyTorch. Filters silence from audio before transcription."""
from typing import Tuple, Optional
import os
import uuid
import logging

import numpy as np
from pydub import AudioSegment
import torch

logger = logging.getLogger(__name__)

def _load_silero() -> Tuple[Optional[object], Optional[object]]:
    """Load Silero VAD model and utils via torch.hub."""
    try:
        model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False)
        logger.info('Silero VAD loaded via torch.hub')
        return model, utils
    except Exception as exc:
        logger.exception('Failed to load silero-vad: %s', exc)
        return None, None

def apply_vad(input_wav_path: str, output_dir: Optional[str] = None) -> Tuple[str, bool]:
    """Apply Silero VAD to the WAV file at `input_wav_path`.
    Returns a tuple (output_path, used_silero=True)
    """
    if output_dir is None:
        output_dir = os.path.dirname(input_wav_path)

    audio = AudioSegment.from_file(input_wav_path)
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    samples = np.array(audio.get_array_of_samples())
    samples_f32 = samples.astype(np.float32) / 32768.0
    input_tensor = torch.from_numpy(samples_f32)

    model, utils = _load_silero()
    if model is None or utils is None:
        raise RuntimeError('Silero VAD model could not be loaded')

    try:
        (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = utils
    except ValueError:
        get_speech_timestamps = utils[0]
        collect_chunks = utils[-1]

    timestamps = get_speech_timestamps(input_tensor, model, sampling_rate=16000)
    speech_tensor = collect_chunks(timestamps, input_tensor)

    if len(speech_tensor) == 0:
        out_path = os.path.join(output_dir, f"{uuid.uuid4().hex}_nospeech.wav")
        silent = AudioSegment.silent(duration=0, frame_rate=16000)
        silent.export(out_path, format='wav')
        return out_path, True

    speech_np = speech_tensor.cpu().numpy()
    int16_bytes = (speech_np * 32767.0).astype(np.int16).tobytes()
    
    out_audio = AudioSegment(
        data=int16_bytes,
        sample_width=2,
        frame_rate=16000,
        channels=1,
    )

    out_path = os.path.join(output_dir, f"{uuid.uuid4().hex}_voiced.wav")
    out_audio.export(out_path, format='wav')
    
    return out_path, True
