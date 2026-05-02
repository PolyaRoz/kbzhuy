import { Tabs } from 'expo-router';
import { StyleSheet, View, Text, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AgentWidget } from '@/components/AgentWidget';

const PRIMARY = '#2B3A2E';
const GRAY = '#6E7E70';

type TabIconProps = {
  name: keyof typeof Ionicons.glyphMap;
  focused: boolean;
  label: string;
};

function TabIcon({ name, focused, label }: TabIconProps) {
  return (
    <View style={styles.tabItem}>
      <Ionicons name={name} size={22} color={focused ? PRIMARY : GRAY} />
      <Text style={[styles.tabLabel, { color: focused ? PRIMARY : GRAY }]}>
        {label}
      </Text>
    </View>
  );
}

export default function TabsLayout() {
  return (
    <View style={{ flex: 1 }}>
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarShowLabel: false,
          tabBarStyle: styles.tabBar,
        }}
      >
        <Tabs.Screen
          name="index"
          options={{
            tabBarIcon: ({ focused }) => (
              <TabIcon name={focused ? 'home' : 'home-outline'} focused={focused} label="Дом" />
            ),
          }}
        />
        <Tabs.Screen
          name="plan"
          options={{
            tabBarIcon: ({ focused }) => (
              <TabIcon name={focused ? 'calendar' : 'calendar-outline'} focused={focused} label="План" />
            ),
          }}
        />
        <Tabs.Screen
          name="cooking"
          options={{
            tabBarIcon: ({ focused }) => (
              <TabIcon name={focused ? 'flame' : 'flame-outline'} focused={focused} label="Готовка" />
            ),
          }}
        />
        <Tabs.Screen
          name="storage"
          options={{
            tabBarIcon: ({ focused }) => (
              <TabIcon name={focused ? 'cube' : 'cube-outline'} focused={focused} label="Хранение" />
            ),
          }}
        />
        <Tabs.Screen
          name="shopping"
          options={{
            tabBarIcon: ({ focused }) => (
              <TabIcon name={focused ? 'cart' : 'cart-outline'} focused={focused} label="Покупки" />
            ),
          }}
        />
        <Tabs.Screen
          name="tray"
          options={{
            tabBarIcon: ({ focused }) => (
              <TabIcon name={focused ? 'newspaper' : 'newspaper-outline'} focused={focused} label="Поднос" />
            ),
          }}
        />
        <Tabs.Screen
          name="agent"
          options={{
            href: null,
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            tabBarIcon: ({ focused }) => (
              <TabIcon name={focused ? 'person' : 'person-outline'} focused={focused} label="Профиль" />
            ),
          }}
        />
      </Tabs>

      {/* Floating agent widget — visible on all screens */}
      <AgentWidget />
    </View>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: '#FAFAF7',
    borderTopWidth: 1,
    borderTopColor: '#D4DAD5',
    height: Platform.OS === 'ios' ? 84 : 64,
    paddingBottom: Platform.OS === 'ios' ? 24 : 8,
    paddingTop: 8,
  },
  tabItem: {
    alignItems: 'center',
    gap: 2,
  },
  tabLabel: {
    fontSize: 9,
    fontWeight: '500',
    letterSpacing: 0.3,
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
  },
});
