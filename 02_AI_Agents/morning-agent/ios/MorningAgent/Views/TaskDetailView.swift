import SwiftUI

struct TaskDetailView: View {
    let taskID: Int
    @State private var task: TaskItem?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if let task {
                    Text(task.title).font(.title2).bold()
                    Text("Status: \(task.status)")
                    Text(task.instructions)

                    if let summary = task.summary {
                        Group {
                            Text("Summary").font(.headline)
                            Text(summary)
                        }
                    }

                    if let transcript = task.transcript {
                        Group {
                            Text("Transcript").font(.headline)
                            Text(transcript)
                                .font(.footnote)
                                .textSelection(.enabled)
                        }
                    }
                } else {
                    ProgressView()
                }
            }
            .padding()
        }
        .navigationTitle("Task")
        .task {
            await load()
        }
    }

    private func load() async {
        do {
            task = try await APIClient.shared.fetchTask(id: taskID)
        } catch {
            print("Load failed:", error)
        }
    }
}
