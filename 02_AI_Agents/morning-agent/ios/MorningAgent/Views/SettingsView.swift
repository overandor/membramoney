import SwiftUI

struct SettingsView: View {
    var body: some View {
        NavigationStack {
            Form {
                Section("Agent") {
                    Text("This assistant places calls on your behalf.")
                    Text("Recommended: always disclose that the assistant is acting for you.")
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
        }
    }
}
