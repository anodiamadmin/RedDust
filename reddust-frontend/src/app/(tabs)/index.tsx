import { StyleSheet, Text, View } from 'react-native';

export default function SoulmateScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>Soulmate Chat (Sara/Syan)</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#121212', // RedDust dark theme background
    justifyContent: 'center',
    alignItems: 'center',
  },
  text: {
    color: '#FFFFFF',
    fontSize: 18,
  },
});