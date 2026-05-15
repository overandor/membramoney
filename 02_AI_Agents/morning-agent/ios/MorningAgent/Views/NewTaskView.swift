import SwiftUI

struct NewTaskView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var title = ""
    @State private var instructions = ""
    @State private var phone = ""
    @State private var isSaving = false

    let onSaved: () async -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("Task") {
                    TextField("Title", text: $title)
                    TextField("Phone number", text: $phone)
                    TextEditor(text: $instructions)
                        .frame(minHeight: 160)
                }
            }
            .navigationTitle("New Task")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Close") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Save") {
                        Task { await save() }
                    }
                    .disabled(isSaving || title.isEmpty || phone.isEmpty || instructions.isEmpty)
                }
            }
        }
    }

    private func save() async {
        guard !isSaving else { return }
        isSaving = true
        defer { isSaving = false }

        do {
            let task = try await APIClient.shared.createTask(
                title: title,
                instructions: instructions,
                phone: phone
            )
            try await APIClient.shared.startTask(id: task.id)
            await onSaved()
            dismiss()
        } catch {
            print("Save failed:", error)
        }
    }
}
