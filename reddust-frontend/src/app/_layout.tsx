import { Stack } from 'expo-router';

export default function RootLayout() {
  return (
    <Stack>
      {/* This points to your (tabs) folder and hides the duplicate header */}
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
    </Stack>
  );
}