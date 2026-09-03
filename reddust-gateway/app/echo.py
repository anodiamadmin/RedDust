import asyncio
from collections import deque
from fractions import Fraction
from pathlib import Path

from aiortc import MediaStreamTrack
from aiortc.contrib.media import MediaPlayer
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame
from av.audio.resampler import AudioResampler


PROMPT_PATH = (
    Path(__file__).resolve().parent
    / "audio"
    / "hello_reddust_echo.wav"
)


class EchoAudioTrack(MediaStreamTrack):
    """
    Step 19B processed echo track.

    Output sequence:

        prerecorded greeting
                ↓
          2-second silence
                ↓
        incoming caller audio
    """

    kind = "audio"

    SAMPLE_RATE = 48000
    SILENCE_SAMPLES = 960

    def __init__(
        self,
        incoming_track,
        delay_seconds: float = 2.0,
    ):
        super().__init__()

        self.incoming_track = incoming_track

        if not PROMPT_PATH.exists():
            raise FileNotFoundError(
                f"Prompt audio file not found: "
                f"{PROMPT_PATH}"
            )

        self.player = MediaPlayer(
            str(PROMPT_PATH)
        )

        self.prompt_track = self.player.audio

        if self.prompt_track is None:
            raise RuntimeError(
                "Prompt file contains no audio track"
            )

        self.prompt_resampler = AudioResampler(
            format="s16",
            layout="mono",
            rate=self.SAMPLE_RATE,
        )

        self.echo_resampler = AudioResampler(
            format="s16",
            layout="mono",
            rate=self.SAMPLE_RATE,
        )

        self.prompt_frames = deque()
        self.echo_frames = deque()

        self.stage = "prompt"

        frame_duration = (
            self.SILENCE_SAMPLES
            / self.SAMPLE_RATE
        )

        self.delay_frames_remaining = round(
            delay_seconds
            / frame_duration
        )

        self.output_pts = 0

        self.next_deadline = None

        self._delay_logged = False
        self._echo_logged = False

        print(
            "EchoAudioTrack: playing "
            "'Hello RedDust Echo!'"
        )

    async def _emit(self, frame):
        """
        Give every outgoing frame a continuous
        48-kHz timeline and prevent queued audio
        from being emitted in a burst.
        """

        frame.sample_rate = self.SAMPLE_RATE

        frame.pts = self.output_pts

        frame.time_base = Fraction(
            1,
            self.SAMPLE_RATE,
        )

        duration = (
            frame.samples
            / self.SAMPLE_RATE
        )

        loop = asyncio.get_running_loop()

        now = loop.time()

        if self.next_deadline is None:
            self.next_deadline = now
        else:
            self.next_deadline += duration

            wait = (
                self.next_deadline
                - now
            )

            if wait > 0:
                await asyncio.sleep(wait)

        self.output_pts += frame.samples

        return frame

    def _make_silence_frame(self):
        """
        Make one 20-ms mono PCM silence frame.
        """

        frame = AudioFrame(
            format="s16",
            layout="mono",
            samples=self.SILENCE_SAMPLES,
        )

        frame.sample_rate = self.SAMPLE_RATE

        for plane in frame.planes:
            plane.update(
                bytes(plane.buffer_size)
            )

        return frame

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        while True:

            # --------------------------------
            # Stage 1 — prerecorded prefix
            # --------------------------------
            if self.stage == "prompt":

                if self.prompt_frames:
                    frame = (
                        self.prompt_frames
                        .popleft()
                    )

                    return await self._emit(
                        frame
                    )

                try:
                    source_frame = (
                        await self.prompt_track.recv()
                    )

                except MediaStreamError:
                    self.stage = "delay"

                    continue

                converted_frames = (
                    self.prompt_resampler
                    .resample(source_frame)
                )

                self.prompt_frames.extend(
                    converted_frames
                )

                continue

            # --------------------------------
            # Stage 2 — two-second delay
            # --------------------------------
            if self.stage == "delay":

                if not self._delay_logged:
                    print(
                        "EchoAudioTrack: "
                        "prefix finished; "
                        "waiting 2 seconds"
                    )

                    self._delay_logged = True

                if (
                    self.delay_frames_remaining
                    > 0
                ):
                    self.delay_frames_remaining -= 1

                    silence = (
                        self._make_silence_frame()
                    )

                    return await self._emit(
                        silence
                    )

                self.stage = "echo"

                continue

            # --------------------------------
            # Stage 3 — echo incoming speech
            # --------------------------------
            if self.stage == "echo":

                if not self._echo_logged:
                    print(
                        "EchoAudioTrack: "
                        "now echoing caller audio"
                    )

                    self._echo_logged = True

                if self.echo_frames:
                    frame = (
                        self.echo_frames
                        .popleft()
                    )

                    return await self._emit(
                        frame
                    )

                source_frame = (
                    await self.incoming_track.recv()
                )

                converted_frames = (
                    self.echo_resampler
                    .resample(source_frame)
                )

                self.echo_frames.extend(
                    converted_frames
                )

    def stop(self):
        if (
            self.prompt_track
            and self.prompt_track.readyState
            == "live"
        ):
            self.prompt_track.stop()

        super().stop()
