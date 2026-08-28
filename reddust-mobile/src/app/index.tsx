import { useRef, useState } from "react";
import { Button, PermissionsAndroid, Platform, Text, View } from "react-native";

import {
  mediaDevices,
  MediaStream,
  RTCPeerConnection,
  RTCSessionDescription,
} from "react-native-webrtc";

/*
 * react-native-webrtc@124.x has a TypeScript typing issue where
 * RTCPeerConnection's event methods are not exposed correctly.
 *
 * The methods exist at runtime, so we define only the event API
 * that RedDust currently needs.
 */
type WebRTCPeerConnectionEvent =
  | "iceconnectionstatechange"
  | "connectionstatechange"
  | "icegatheringstatechange";

type WebRTCPeerConnectionEventTarget = {
  addEventListener: (
    type: WebRTCPeerConnectionEvent,
    listener: () => void,
  ) => void;

  removeEventListener: (
    type: WebRTCPeerConnectionEvent,
    listener: () => void,
  ) => void;
};

/*
 * Current RedDust Gateway address.
 *
 * If the laptop's Wi-Fi IPv4 address changes,
 * update this value.
 */
const GATEWAY_URL = "http://192.168.1.8:8000/offer";

export default function HomeScreen() {
  const [status, setStatus] = useState("Microphone not started");

  const [stream, setStream] = useState<MediaStream | null>(null);

  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);

  /*
   * Request microphone permission.
   *
   * Android:
   * Explicitly requests RECORD_AUDIO.
   *
   * iOS:
   * getUserMedia() triggers the native iOS
   * microphone permission dialog.
   *
   * NSMicrophoneUsageDescription must already
   * exist in app.json / Info.plist.
   */
  const requestMicrophonePermission = async () => {
    if (Platform.OS === "android") {
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
    }

    if (Platform.OS === "ios") {
      return true;
    }

    return false;
  };

  /*
   * Step 11 + Step 16
   *
   * Create the RTCPeerConnection and install
   * WebRTC state monitoring.
   */
  const createPeerConnection = () => {
    const pc = new RTCPeerConnection({
      iceServers: [
        {
          urls: "stun:stun.l.google.com:19302",
        },
      ],
    });

    /*
     * TypeScript adapter for the event methods that
     * react-native-webrtc provides at runtime.
     */
    const eventPc = pc as unknown as WebRTCPeerConnectionEventTarget;

    peerConnectionRef.current = pc;

    console.log("RTCPeerConnection created");

    /*
     * Step 16 — initial states.
     *
     * Event handlers only fire when the state changes,
     * so log the starting values explicitly.
     */
    console.log("Initial ICE connection state:", pc.iceConnectionState);

    console.log("Initial PeerConnection state:", pc.connectionState);

    /*
     * Step 16 — monitor ICE connectivity.
     *
     * This tells us whether the Samsung and
     * FastAPI/aiortc gateway can find a working
     * network path.
     */
    eventPc.addEventListener("iceconnectionstatechange", () => {
      console.log("ICE:", pc.iceConnectionState);

      if (pc.iceConnectionState === "checking") {
        setStatus("WebRTC ICE connection checking...");
      }

      if (
        pc.iceConnectionState === "connected" ||
        pc.iceConnectionState === "completed"
      ) {
        setStatus(`ICE connected: ${pc.iceConnectionState}`);
      }

      if (pc.iceConnectionState === "failed") {
        setStatus("WebRTC ICE connection failed");
      }

      if (pc.iceConnectionState === "disconnected") {
        setStatus("WebRTC ICE connection disconnected");
      }

      if (pc.iceConnectionState === "closed") {
        console.log("ICE connection closed");
      }
    });

    /*
     * Step 16 — monitor the overall
     * RTCPeerConnection state.
     *
     * Main success target:
     *
     * new
     *   ↓
     * connecting
     *   ↓
     * connected
     */
    eventPc.addEventListener("connectionstatechange", () => {
      console.log("Connection:", pc.connectionState);

      if (pc.connectionState === "connecting") {
        setStatus("WebRTC connection establishing...");
      }

      if (pc.connectionState === "connected") {
        setStatus("WebRTC connection connected");
      }

      if (pc.connectionState === "failed") {
        setStatus("WebRTC connection failed");
      }

      if (pc.connectionState === "disconnected") {
        setStatus("WebRTC connection disconnected");
      }

      if (pc.connectionState === "closed") {
        console.log("PeerConnection closed");
      }
    });

    return pc;
  };

  /*
   * We are currently NOT using trickle ICE.
   *
   * Therefore, after setLocalDescription(),
   * wait until ICE gathering is complete before
   * sending the SDP offer to FastAPI.
   */
  const waitForIceGatheringComplete = async (pc: RTCPeerConnection) => {
    if (pc.iceGatheringState === "complete") {
      console.log("ICE gathering already complete");

      return;
    }

    const eventPc = pc as unknown as WebRTCPeerConnectionEventTarget;

    await new Promise<void>((resolve) => {
      const checkState = () => {
        console.log("ICE gathering state:", pc.iceGatheringState);

        if (pc.iceGatheringState === "complete") {
          eventPc.removeEventListener("icegatheringstatechange", checkState);

          resolve();
        }
      };

      eventPc.addEventListener("icegatheringstatechange", checkState);
    });
  };

  const startMicrophone = async () => {
    try {
      /*
       * Prevent multiple microphone streams /
       * PeerConnections from repeated taps.
       */
      if (stream) {
        setStatus("Microphone is already running");

        return;
      }

      /*
       * Request microphone permission.
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

      /*
       * Verify that the microphone produced
       * an audio track.
       */
      const audioTracks = localStream.getAudioTracks();

      console.log("Audio tracks:", audioTracks);

      /*
       * Create the WebRTC PeerConnection.
       *
       * Step 16 state listeners are installed
       * inside createPeerConnection().
       */
      const pc = createPeerConnection();

      /*
       * Step 12 — attach the microphone
       * track to the PeerConnection.
       */
      localStream.getTracks().forEach((track) => {
        pc.addTrack(track, localStream);
      });

      console.log("Microphone track added to RTCPeerConnection");

      /*
       * Step 13 — create the WebRTC offer.
       */
      const offer = await pc.createOffer();

      console.log("WebRTC offer created");

      console.log("Offer type:", offer.type);

      console.log("Initial Offer SDP:", offer.sdp);

      /*
       * Adopt the offer locally.
       *
       * This also begins ICE candidate gathering.
       */
      await pc.setLocalDescription(offer);

      console.log("Local description set");

      /*
       * Because we are using one-shot HTTP
       * signaling instead of trickle ICE,
       * wait for all ICE candidates.
       */
      setStatus("Gathering ICE candidates...");

      await waitForIceGatheringComplete(pc);

      console.log("ICE gathering complete");

      /*
       * pc.localDescription now contains
       * the completed offer including ICE
       * candidates.
       */
      const localDescription = pc.localDescription;

      if (!localDescription) {
        throw new Error("PeerConnection has no local description");
      }

      console.log("Final local description type:", localDescription.type);

      console.log("Final local SDP:", localDescription.sdp);

      /*
       * Step 14 — send the completed offer
       * to FastAPI / aiortc.
       */
      setStatus("Sending WebRTC offer to gateway...");

      const response = await fetch(GATEWAY_URL, {
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
       * Stop if FastAPI returns an HTTP error.
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
       * Step 15 — apply the gateway's
       * answer to the Samsung PeerConnection.
       */
      setStatus("Applying gateway WebRTC answer...");

      await pc.setRemoteDescription(new RTCSessionDescription(answer));

      console.log("Remote description set");

      /*
       * Step 15 is complete.
       *
       * Step 16 listeners now continue watching
       * for:
       *
       * ICE: connected/completed
       * Connection: connected
       *
       * Do not overwrite the status here,
       * because one of those state events may
       * already have updated it.
       */
      console.log(
        `WebRTC signaling complete. Audio tracks: ${audioTracks.length}`,
      );
    } catch (error) {
      console.error("Microphone/WebRTC error:", error);

      setStatus(`Microphone/WebRTC error: ${String(error)}`);
    }
  };

  const stopMicrophone = () => {
    /*
     * Stop the local microphone tracks.
     */
    if (stream) {
      stream.getTracks().forEach((track) => {
        track.stop();
      });

      setStream(null);
    }

    /*
     * Close the current WebRTC PeerConnection.
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
