#!/bin/bash

# Exit script on any error
set -e

IPA_PATH="$1"

# Check if IPA path parameter is provided
if [ -z "$IPA_PATH" ]; then
    echo "Error: Please provide a path to an IPA file."
    echo "Usage: ./install-ios-ipa.sh /path/to/SpontaneousAI.ipa"
    exit 1
fi

echo "Starting code signing and installation process..."

# 1. Locate personal Apple Development signing identity in Keychain
EXPANDED_CODE_SIGN_IDENTITY=$(security find-identity -v -p codesigning | grep "Apple Development" | head -n 1 | awk -F'"' '{print $2}')

if [ -z "$EXPANDED_CODE_SIGN_IDENTITY" ]; then
    echo "Error: No Apple Development signing certificate found in Keychain."
    echo "Solution: Open Xcode once, go to Settings -> Accounts, and sign in with your free Apple ID."
    exit 1
fi

echo "Using signing identity: $EXPANDED_CODE_SIGN_IDENTITY"

# 2. Create temporary working directory for extraction
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Extracting IPA file..."
unzip -q "$IPA_PATH" -d "$TEMP_DIR"

APP_PATH=$(find "$TEMP_DIR/Payload" -name "*.app" -maxdepth 1)

if [ -z "$APP_PATH" ]; then
    echo "Error: Could not find .app bundle inside Payload directory of the IPA."
    exit 1
fi

# 3. Resign app bundle using local identity
echo "Resigning app bundle..."
codesign --force --deep --sign "$EXPANDED_CODE_SIGN_IDENTITY" "$APP_PATH"

# 4. Detect connected iPhone via USB
echo "Searching for connected iPhone..."
DEVICE_ID=$(xcrun devicectl list devices | grep -i "iPhone" | head -n 1 | awk '{print $1}')

if [ -z "$DEVICE_ID" ]; then
    echo "Error: No connected iPhone found via USB. Please connect your iPhone and tap 'Trust This Computer'."
    exit 1
fi

echo "Installing application onto device: $DEVICE_ID"

# 5. Install app using devicectl
xcrun devicectl device install app --device "$DEVICE_ID" "$APP_PATH"

echo "Installation completed successfully! SpontaneousAI is installed on your iPhone."
