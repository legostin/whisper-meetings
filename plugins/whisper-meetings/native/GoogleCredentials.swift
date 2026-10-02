import Foundation
import Security

// Tokens pass through stdin/stdout, never command-line arguments or logs.
@main struct GoogleCredentials {
    static func main() {
        guard CommandLine.arguments.count == 3 else { exit(2) }
        let operation = CommandLine.arguments[1]
        let account = CommandLine.arguments[2]
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "in.legost.whisper-meetings.google", kSecAttrAccount as String: account]
        var status: OSStatus = errSecParam
        switch operation {
        case "read":
            var lookup = query
            lookup[kSecReturnData as String] = true
            lookup[kSecMatchLimit as String] = kSecMatchLimitOne
            var result: CFTypeRef?
            status = SecItemCopyMatching(lookup as CFDictionary, &result)
            if status == errSecItemNotFound { exit(3) }
            if status == errSecSuccess, let data = result as? Data {
                FileHandle.standardOutput.write(data)
            }
        case "write":
            let data = FileHandle.standardInput.readDataToEndOfFile()
            guard !data.isEmpty, data.count < 65536 else { exit(2) }
            status = SecItemUpdate(query as CFDictionary, [kSecValueData as String: data] as CFDictionary)
            if status == errSecItemNotFound {
                var addition = query
                addition[kSecValueData as String] = data
                addition[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
                status = SecItemAdd(addition as CFDictionary, nil)
            }
        case "delete":
            status = SecItemDelete(query as CFDictionary)
            if status == errSecItemNotFound { status = errSecSuccess }
        default: exit(2)
        }
        if status != errSecSuccess {
            FileHandle.standardError.write(Data("Google credential storage unavailable (\(status)).\n".utf8))
            exit(1)
        }
    }
}
