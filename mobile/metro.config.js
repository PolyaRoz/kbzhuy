const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const config = getDefaultConfig(__dirname);

// Ensure single copies of react-navigation packages to prevent conflicts
config.resolver.resolveRequest = (context, moduleName, platform) => {
  // Force all react-navigation imports to use the single top-level copy
  if (
    moduleName.startsWith('@react-navigation/') ||
    moduleName === 'react-native-screens' ||
    moduleName === 'react-native-safe-area-context'
  ) {
    const resolvedPath = require.resolve(moduleName, {
      paths: [path.resolve(__dirname, 'node_modules')],
    });
    return { type: 'sourceFile', filePath: resolvedPath };
  }
  return context.resolveRequest(context, moduleName, platform);
};

module.exports = config;
