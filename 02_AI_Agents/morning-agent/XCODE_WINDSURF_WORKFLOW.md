# Xcode Once, Windsurf After - 10 Step Workflow

## Overview
Use Xcode once to create the project structure, then use Windsurf for 90% of coding. Return to Xcode only for build, sign, archive, and App Store submission.

## Step 1: Create Project in Xcode
- Open Xcode
- File > New > Project
- Choose "App" under iOS tab
- Enter product name: `MorningAgent`
- Choose Interface: SwiftUI
- Choose Language: Swift
- Choose storage: None (for MVP)
- Save to: `ios/MorningAgent` folder
- Close Xcode after creation

## Step 2: Verify Project Structure
Your Xcode project should have:
- `MorningAgent.xcodeproj` (the project file)
- `MorningAgent/` folder with:
  - `MorningAgentApp.swift`
  - `ContentView.swift`
  - `Assets.xcassets`
  - `Preview Content`

## Step 3: Open in Windsurf
- Open the `ios/MorningAgent` folder in Windsurf
- You can now edit all Swift files in Windsurf
- Windsurf will handle:
  - Writing new Swift files
  - Refactoring code
  - Generating screens, models, services
  - Editing existing code

## Step 4: Copy Generated Files to Xcode Project
For the Morning Agent scaffold I created:
- Copy `Models/TaskItem.swift` to `MorningAgent/Models/`
- Copy `Services/APIClient.swift` to `MorningAgent/Services/`
- Copy `Views/*.swift` to `MorningAgent/Views/`
- Replace `ContentView.swift` with the new version
- Replace `MorningAgentApp.swift` with the new version

**Important:** You need to add these files to Xcode's project navigator:
- Open Xcode
- Right-click the appropriate group (e.g., Views)
- "Add Files to MorningAgent..."
- Select the new files
- Make sure "Copy items if needed" is unchecked (files already exist)
- Click Add

## Step 5: Configure Build Settings in Xcode
- Open Xcode
- Select the project in navigator
- Select the target
- In "Signing & Capabilities":
  - Select your development team
  - Enable "Automatically manage signing"
- In "Build Settings":
  - Set iOS Deployment Target (e.g., iOS 17.0)
  - Verify Swift Language Version

## Step 6: Test in Simulator (Xcode)
- In Xcode, select a simulator (e.g., iPhone 15)
- Press Cmd+R to build and run
- Verify the app launches
- Test basic navigation
- If there are build errors, fix them in Windsurf, then rebuild

## Step 7: Day-to-Day Coding in Windsurf
For ongoing development:
- Stay in Windsurf for:
  - Adding new views
  - Modifying existing views
  - Creating new models
  - Writing service code
  - Refactoring
  - Bug fixes
- After making changes:
  - Save files in Windsurf
  - Switch to Xcode
  - Press Cmd+R to test
  - Return to Windsurf for more coding

## Step 8: Periodic Xcode Sync
Every few hours or after major changes:
- Open Xcode
- Cmd+R to build and run
- Check for any Xcode-specific issues:
  - Missing file references
  - Build settings
  - Asset catalog issues
  - Preview provider issues
- Fix issues in Windsurf if they're code-related
- Fix issues in Xcode if they're project-related

## Step 9: Device Testing (Xcode)
- Connect your iPhone to Mac
- In Xcode, select your device from the simulator dropdown
- Press Cmd+R to build and run on device
- Test on real hardware
- Fix any device-specific issues in Windsurf

## Step 10: Archive and Submit (Xcode Only)
When ready for App Store:
- In Xcode: Product > Archive
- Xcode Organizer opens
- Validate your archive
- Distribute App:
  - Choose "App Store Connect"
  - Follow the upload wizard
- Complete submission in App Store Connect:
  - Add screenshots
  - Set pricing
  - Submit for review

## Summary Table

| Task | Tool | Reason |
|------|------|--------|
| Create project | Xcode | Apple's official project structure |
| Write Swift code | Windsurf | AI assistance, faster coding |
| Refactor | Windsurf | AI-powered refactoring |
| Generate screens | Windsurf | AI generates SwiftUI views |
| Add files to project | Xcode | Project file management |
| Build settings | Xcode | Apple-specific configuration |
| Sign & capabilities | Xcode | Code signing required by Apple |
| Simulator testing | Xcode | Apple's simulator |
| Device testing | Xcode | Device deployment |
| Archive | Xcode | Archive generation |
| App Store submission | Xcode + App Store Connect | Official submission flow |

## Pro Tips

1. **Keep Xcode open in background** - Quick Cmd+R to test after Windsurf changes
2. **Use Git** - Commit after major changes, easy to revert if Xcode breaks
3. **File organization** - Keep the same folder structure in Windsurf as Xcode expects
4. **Preview issues** - SwiftUI Previews may break in Windsurf - ignore them, test in Xcode
5. **Asset catalog** - Use Xcode for images, icons, colors - Windsurf can't edit these easily
6. **Info.plist** - Edit in Xcode if you need to add permissions (camera, microphone, etc.)

## Common Issues

**"File not found" build error:**
- File exists on disk but not in Xcode project
- Fix: Right-click group > Add Files to MorningAgent

**"No such module" error:**
- Missing Swift Package or framework
- Fix: File > Add Package in Xcode

**Signing errors:**
- Team not selected or certificate expired
- Fix: Xcode > Preferences > Accounts, or re-enable automatic signing

**Preview crashes:**
- SwiftUI Preview issues are common
- Fix: Ignore previews, test in simulator instead

## When to Use Each Tool

**Use Windsurf for:**
- Writing new Swift code
- Modifying existing code
- Generating boilerplate
- Refactoring
- Adding new features
- Fixing bugs

**Use Xcode for:**
- Initial project creation
- Adding files to project navigator
- Configuring build settings
- Code signing
- Running in simulator
- Device testing
- Archiving
- App Store submission
- Editing Info.plist
- Managing assets (images, icons)
- Adding Swift Packages
