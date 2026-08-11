import { useRef, useState } from "react";
import { Button, PermissionsAndroid, Platform, Text, View } from "react-native";

import {
  mediaDevices,
  MediaStream,
  RTCPeerConnection,
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

  const startMicrophone = async () => {
    try {
      if (stream) {
        setStatus("Microphone is already running");
        return;
      }

      const hasPermission = await requestMicrophonePermission();

      if (!hasPermission) {
        setStatus("Microphone permission denied");
        return;
      }

      setStatus("Starting microphone...");

      const localStream = await mediaDevices.getUserMedia({
        audio: true,
        video: false,
      });

      setStream(localStream);

      const pc = createPeerConnection();

      localStream.getTracks().forEach((track) => {
        pc.addTrack(track, localStream);
      });

      console.log("Microphone track added to RTCPeerConnection");

      // Step 13 — create the WebRTC offer
      const offer = await pc.createOffer();

      console.log("WebRTC offer created");
      console.log("Offer type:", offer.type);
      console.log("Offer SDP:", offer.sdp);

      // Tell the PeerConnection to use this offer
      await pc.setLocalDescription(offer);

      console.log("Local description set");

      const audioTracks = localStream.getAudioTracks();

      console.log("Audio tracks:", audioTracks);

      setStatus(
        `Microphone connected to PeerConnection. Audio tracks: ${audioTracks.length}`,
      );
    } catch (error) {
      console.error("Microphone error:", error);
      setStatus(`Microphone error: ${String(error)}`);
    }
  };

  const stopMicrophone = () => {
    if (stream) {
      stream.getTracks().forEach((track) => {
        track.stop();
      });

      setStream(null);
    }

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
