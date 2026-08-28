from fastapi import FastAPI
from pydantic import BaseModel
from aiortc import RTCPeerConnection, RTCSessionDescription
from app.echo import EchoAudioTrack

app = FastAPI()

peer_connections = set()


class Offer(BaseModel):
    sdp: str
    type: str


@app.get("/")
async def root():
    return {"status": "RedDust Gateway running"}


@app.post("/offer")
async def offer(offer: Offer):
    pc = RTCPeerConnection()
    peer_connections.add(pc)
    
    print("Gateway RTCPeerConnection created")
    
    @pc.on("track")
    def on_track(track):
        print("Gateway received track:", track.kind)

        if track.kind == "audio":
            echo_track = EchoAudioTrack(track)

            pc.addTrack(echo_track)

            print("Gateway echo audio track added")
    
    remote_offer = RTCSessionDescription(
        sdp=offer.sdp,
        type=offer.type,
    )
    
    await pc.setRemoteDescription(remote_offer)
    
    print("Gateway remote description set")
    
    answer = await pc.createAnswer()
    
    await pc.setLocalDescription(answer)
    
    print("Gateway answer created")
    
    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    }
