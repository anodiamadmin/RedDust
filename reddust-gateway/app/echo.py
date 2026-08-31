from aiortc import MediaStreamTrack


class EchoAudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, incoming_track):
        super().__init__()
        self.incoming_track = incoming_track

    async def recv(self):
        frame = await self.incoming_track.recv()
        return frame
