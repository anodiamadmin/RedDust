from fastapi import FastAPI
from pydantic import BaseModel

from aiortc import RTCPeerConnection, RTCSessionDescription

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

    remote_offer = RTCSessionDescription(
        sdp=offer.sdp,
        type=offer.type,
    )

    await pc.setRemoteDescription(remote_offer)

    answer = await pc.createAnswer()

    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    }
