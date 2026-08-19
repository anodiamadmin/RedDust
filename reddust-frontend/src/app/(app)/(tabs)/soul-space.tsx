import { StyleSheet, Text, View } from 'react-native';

export default function SoulSpaceScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>Soul Space</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#121212',
    justifyContent: 'center',
    alignItems: 'center',
  },
  text: {
    color: '#FFFFFF',
    fontSize: 18,
  },
});
