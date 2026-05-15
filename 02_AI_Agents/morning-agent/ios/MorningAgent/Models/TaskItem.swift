import Foundation

struct TaskItem: Codable, Identifiable {
    let id: Int
    let title: String
    let instructions: String
    let phoneNumber: String?
    let status: String
    let callSid: String?
    let transcript: String?
    let summary: String?

    enum CodingKeys: String, CodingKey {
        case id, title, instructions, status, transcript, summary
        case phoneNumber = "phone_number"
        case callSid = "call_sid"
    }
}

struct CreateTaskRequest: Codable {
    let title: String
    let instructions: String
    let phone_number: String
}
