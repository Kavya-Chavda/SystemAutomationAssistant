import queue
import logging
import time
import numpy as np
import sounddevice as sd
from src.voice.speech_to_text_whisper import SpeechToTextWhisper

logger = logging.getLogger(__name__)

class VoiceListener:
    def __init__(self):
        self.sample_rate = 16000
        # Default to Whisper now
        self.stt = SpeechToTextWhisper(model_size="medium.en")
        self._stop_event = False
        
    def stop(self):
        self._stop_event = True
        
    def listen(self, silence_threshold: float = 0.01, silence_duration: float = 1.5, manual_stop_only: bool = False, device=None) -> dict:
        """
        Listens to the microphone using an energy-based silence detector.
        Returns a dict containing transcript and metadata: {transcript, duration, model, device}
        """
        q = queue.Queue()

        def callback(indata, _frames, _time_info, status):
            if status:
                logger.warning(f"Audio status: {status}")
            # Put float32 frames into queue
            q.put(indata.copy())

        logger.info("VoiceListener starting...")
        
        audio_buffer = []
        is_recording = False
        silence_start_time = None
        start_time = time.time()
        
        self._stop_event = False
        try:
            device_kwarg = int(device) if device and device != "default" else None
            with sd.InputStream(samplerate=self.sample_rate, blocksize=8000, dtype='float32',
                                   channels=1, callback=callback, device=device_kwarg):
                while True:
                    if self._stop_event:
                        logger.info("VoiceListener stopped manually.")
                        break
                        
                    data = q.get()
                    audio_buffer.append(data)
                    
                    if not manual_stop_only:
                        rms = np.sqrt(np.mean(data**2))
                        
                        if rms > silence_threshold:
                            is_recording = True
                            silence_start_time = None
                        elif is_recording:
                            if silence_start_time is None:
                                silence_start_time = time.time()
                            elif time.time() - silence_start_time > silence_duration:
                                break

                            
        except sd.PortAudioError as e:
            logger.error(f"Microphone error (PortAudio): {e}")
        except Exception as e:
            logger.error(f"Voice listener error: {e}", exc_info=True)

        if not audio_buffer:
            return {}
            
        full_audio = np.concatenate(audio_buffer).flatten()
        result = self.stt.process_audio(full_audio)
        return result
