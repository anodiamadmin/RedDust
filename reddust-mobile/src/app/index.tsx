import { useRef, useState } from "react";
import { Button, PermissionsAndroid, Platform, Text, View } from "react-native";

import {
  mediaDevices,
  MediaStream,
  RTCPeerConnection,
  RTCSessionDescription,
} from "react-native-webrtc";

export default function HomeScreen() {
  const [status, setStatus] = useState("Microphone not started");
  const [stream, setStream] = useState<MediaStream | null>(null);

  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);

  const requestMicrophonePermission = async () => {
    if (Platform.OS !== "android") {
      return true;
    }

    const result = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
      {
        title: "Microphone Permission",
        message:
          "RedDust needs microphone access for real-time voice conversations.",
        buttonPositive: "Allow",
        buttonNegative: "Cancel",
      },
    );

    return result === PermissionsAndroid.RESULTS.GRANTED;
  };

  const createPeerConnection = () => {
    const pc = new RTCPeerConnection({
      iceServers: [
        {
          urls: "stun:stun.l.google.com:19302",
        },
      ],
    });

    peerConnectionRef.current = pc;

    console.log("RTCPeerConnection created");

    return pc;
  };

  /*
   * For this first RedDust proof of concept we are NOT using
   * trickle ICE signalling.
   *
   * Therefore, after setLocalDescription(), we wait until
   * WebRTC has finished gathering ICE candidates before
   * sending the SDP offer to FastAPI.
   */
  const waitForIceGatheringComplete = async (pc: RTCPeerConnection) => {
    if (pc.iceGatheringState === "complete") {
      console.log("ICE gathering already complete");
      return;
    }

    await new Promise<void>((resolve) => {
      const checkState = () => {
        console.log("ICE gathering state:", pc.iceGatheringState);

        if (pc.iceGatheringState === "complete") {
          pc.removeEventListener("icegatheringstatechange", checkState);

          resolve();
        }
      };

      pc.addEventListener("icegatheringstatechange", checkState);
    });
  };

  const startMicrophone = async () => {
    try {
      /*
       * Prevent accidentally creating multiple microphone
       * streams / PeerConnections.
       */
      if (stream) {
        setStatus("Microphone is already running");
        return;
      }

      /*
       * Request Android runtime microphone permission.
       */
      const hasPermission = await requestMicrophonePermission();

      if (!hasPermission) {
        setStatus("Microphone permission denied");
        return;
      }

      setStatus("Starting microphone...");

      /*
       * Capture microphone audio.
       */
      const localStream = await mediaDevices.getUserMedia({
        audio: true,
        video: false,
      });

      setStream(localStream);

      const audioTracks = localStream.getAudioTracks();

      console.log("Audio tracks:", audioTracks);

      /*
       * Create the WebRTC PeerConnection.
       */
      const pc = createPeerConnection();

      /*
       * Step 12 — attach microphone track(s)
       * to the PeerConnection.
       */
      localStream.getTracks().forEach((track) => {
        pc.addTrack(track, localStream);
      });

      console.log("Microphone track added to RTCPeerConnection");

      /*
       * Step 13 — create the WebRTC SDP offer.
       */
      const offer = await pc.createOffer();

      console.log("WebRTC offer created");
      console.log("Offer type:", offer.type);
      console.log("Initial Offer SDP:", offer.sdp);

      /*
       * Adopt the offer locally.
       *
       * This also starts ICE candidate gathering.
       */
      await pc.setLocalDescription(offer);

      console.log("Local description set");

      /*
       * IMPORTANT:
       *
       * Because we are currently using one HTTP POST instead
       * of trickle ICE, wait until ICE gathering finishes.
       */
      setStatus("Gathering ICE candidates...");

      await waitForIceGatheringComplete(pc);

      console.log("ICE gathering complete");

      /*
       * The final localDescription should now contain the
       * gathered ICE candidates.
       *
       * Send THIS SDP rather than the original offer.sdp.
       */
      const localDescription = pc.localDescription;

      if (!localDescription) {
        throw new Error("PeerConnection has no local description");
      }

      console.log("Final local description type:", localDescription.type);

      console.log("Final local SDP:", localDescription.sdp);

      /*
       * Step 14 — send the WebRTC offer to FastAPI.
       *
       * 192.168.1.8 is the current Wi-Fi IPv4 address
       * of the Windows laptop running reddust-gateway.
       */
      setStatus("Sending WebRTC offer to gateway...");

      const response = await fetch("http://192.168.1.8:8000/offer", {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          sdp: localDescription.sdp,
          type: localDescription.type,
        }),
      });

      /*
       * Make HTTP errors visible rather than trying
       * to process an invalid response as an SDP answer.
       */
      if (!response.ok) {
        throw new Error(`Gateway returned HTTP ${response.status}`);
      }

      /*
       * FastAPI returns:
       *
       * {
       *   "sdp": "...",
       *   "type": "answer"
       * }
       */
      const answer = await response.json();

      console.log("Gateway answer received");
      console.log("Answer type:", answer.type);
      console.log("Answer SDP:", answer.sdp);

      /*
       * Step 15 — apply the gateway's SDP answer
       * to the Samsung's PeerConnection.
       */
      setStatus("Applying gateway WebRTC answer...");

      await pc.setRemoteDescription(new RTCSessionDescription(answer));

      console.log("Remote description set");

      /*
       * Step 15 has now completed successfully.
       */
      setStatus(
        `WebRTC signaling complete. Answer applied. Audio tracks: ${audioTracks.length}`,
      );
    } catch (error) {
      console.error("Microphone/WebRTC error:", error);

      setStatus(`Microphone/WebRTC error: ${String(error)}`);
    }
  };

  const stopMicrophone = () => {
    /*
     * Stop all microphone tracks.
     */
    if (stream) {
      stream.getTracks().forEach((track) => {
        track.stop();
      });

      setStream(null);
    }

    /*
     * Close the WebRTC PeerConnection.
     */
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }

    setStatus("Microphone and PeerConnection stopped");
  };

  return (
    <View
      style={{
        flex: 1,
        justifyContent: "center",
        alignItems: "center",
        padding: 24,
        gap: 20,
      }}
    >
      <Text
        style={{
          fontSize: 22,
          fontWeight: "bold",
        }}
      >
        RedDust WebRTC Test
      </Text>

      <Text>{status}</Text>

      <Button
        title="Start Microphone"
        onPress={startMicrophone}
        disabled={stream !== null}
      />

      <Button
        title="Stop Microphone"
        onPress={stopMicrophone}
        disabled={stream === null}
      />
    </View>
  );
}
