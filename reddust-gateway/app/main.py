from fastapi import FastAPI
from pydantic import BaseModel
from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from app.echo import EchoAudioTrack
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logging.getLogger("aioice").setLevel(logging.DEBUG)

app = FastAPI()

peer_connections = set()


class Offer(BaseModel):
    sdp: str
    type: str


@app.get("/")
async def root():
    return {"status": "RedDust Gateway running NOW"}


@app.post("/offer")
async def offer(offer: Offer):
    pc = RTCPeerConnection(
        configuration=RTCConfiguration(
            iceServers=[
                RTCIceServer(urls=os.getenv("TURN_SERVER_URL_1")),
                RTCIceServer(
                    urls=[
                        os.getenv("TURN_SERVER_URL_2"),
                        os.getenv("TURN_SERVER_URL_3"),
                        os.getenv("TURN_SERVER_URL_4"),
                        os.getenv("TURN_SERVER_URL_5"),
                    ],
                    username=os.getenv("TURN_USERNAME"),
                    credential=os.getenv("TURN_CREDENTIAL"),
                ),
            ]
        )
    )
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


@app.get("/healthz")
async def healthz():
    return {
        "status": "all-ok",
        "service": "reddust-gateway-here"
    }