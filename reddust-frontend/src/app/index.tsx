// src/app/index.tsx

import { Redirect } from 'expo-router';

export default function Index() {
  // Instantly push the app to check the sign-in screen
  return <Redirect href="/signin" />;
}