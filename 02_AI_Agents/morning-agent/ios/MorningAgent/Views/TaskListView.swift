import SwiftUI

struct TaskListView: View {
    @State private var tasks: [TaskItem] = []
    @State private var showingNewTask = false
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            List(tasks) { task in
                NavigationLink(destination: TaskDetailView(taskID: task.id)) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(task.title).font(.headline)
                        Text(task.status.capitalized)
                            .font(.subheadline)
                        if let summary = task.summary, !summary.isEmpty {
                            Text(summary)
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                    }
                }
            }
            .navigationTitle("Morning Agent")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showingNewTask = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showingNewTask) {
                NewTaskView {
                    await load()
                }
            }
            .task {
                await load()
            }
            .refreshable {
                await load()
            }
        }
    }

    private func load() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            tasks = try await APIClient.shared.fetchTasks()
        } catch {
            print("Failed to fetch tasks:", error)
        }
    }
}
