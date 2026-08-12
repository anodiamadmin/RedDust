import { MaterialIcons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function TabLayout() {
  const insets = useSafeAreaInsets();

  return (
    <Tabs
      screenOptions={{
        headerShown: false, 
        tabBarStyle: {
          backgroundColor: '#1C1C1E', 
          borderTopWidth: 0, 
          // 3. Add the bottom inset to your height and padding
          height: 60 + insets.bottom, 
          paddingBottom: 10 + insets.bottom, 
          paddingTop: 5,
        },
        tabBarActiveTintColor: '#EF4444', 
        tabBarInactiveTintColor: '#8E8E93',
      }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'Soulmate',
          tabBarIcon: ({ color, size }) => (
            <MaterialIcons name="mic" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="soul-space"
        options={{
          title: 'Soul Space',
          tabBarIcon: ({ color, size }) => (
            <MaterialIcons name="favorite-border" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}