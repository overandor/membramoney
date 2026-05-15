import Foundation

@MainActor
final class APIClient: ObservableObject {
    static let shared = APIClient()

    private let baseURL = URL(string: "http://localhost:8000")!

    func fetchTasks() async throws -> [TaskItem] {
        let (data, _) = try await URLSession.shared.data(from: baseURL.appendingPathComponent("tasks"))
        return try JSONDecoder().decode([TaskItem].self, from: data)
    }

    func createTask(title: String, instructions: String, phone: String) async throws -> TaskItem {
        var request = URLRequest(url: baseURL.appendingPathComponent("tasks"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(
            CreateTaskRequest(title: title, instructions: instructions, phone_number: phone)
        )

        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(TaskItem.self, from: data)
    }

    func startTask(id: Int) async throws {
        var request = URLRequest(url: baseURL.appendingPathComponent("tasks/\(id)/start"))
        request.httpMethod = "POST"
        _ = try await URLSession.shared.data(for: request)
    }

    func fetchTask(id: Int) async throws -> TaskItem {
        let (data, _) = try await URLSession.shared.data(from: baseURL.appendingPathComponent("tasks/\(id)"))
        return try JSONDecoder().decode(TaskItem.self, from: data)
    }
}
