// Native iOS RoomPlan measurement companion for the Library Contents Claim Agent.
// Requires iOS 16+, a RoomPlan-supported device, camera permission and an Xcode iOS target.
// Export the JSON summary and import it into an active browser sweep. A supported iPhone/iPad
// is required; this does not make a desktop webcam metric-capable.

import SwiftUI
import RoomPlan

struct RoomPlanScannerView: View {
    @State private var scanAvailable = RoomCaptureSession.isSupported
    @State private var exportedJSON: String = ""
    @State private var showingResult = false
    @State private var stopRequested = false
    @State private var serverBaseURL = "http://192.168.1.10:4178"
    @State private var sweepID = ""
    @State private var uploadStatus = "Scan a room, then send measurements to the active sweep."
    @State private var uploading = false

    var body: some View {
        NavigationStack {
            Group {
                if scanAvailable {
                    VStack(spacing: 12) {
                        RoomCaptureHost(exportedJSON: $exportedJSON, stopRequested: $stopRequested)
                            .ignoresSafeArea(edges: .bottom)
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Connect to active inventory sweep").font(.headline)
                            TextField("Backend URL (use computer LAN IP)", text: $serverBaseURL)
                                .textInputAutocapitalization(.never).keyboardType(.URL).autocorrectionDisabled()
                                .textFieldStyle(.roundedBorder)
                            TextField("Active sweep ID", text: $sweepID)
                                .textInputAutocapitalization(.never).autocorrectionDisabled()
                                .textFieldStyle(.roundedBorder)
                            Button {
                                Task { await uploadMeasurements() }
                            } label: {
                                if uploading { ProgressView() } else { Label("Send measurements to active sweep", systemImage: "arrow.up.circle.fill") }
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(exportedJSON.isEmpty || sweepID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || uploading)
                            Text(uploadStatus).font(.caption).foregroundStyle(.secondary)
                        }
                        .padding(.horizontal).padding(.bottom, 8)
                    }
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "viewfinder").font(.largeTitle)
                        Text("Room scanning unavailable").font(.headline)
                        Text("This device cannot run RoomPlan. Use the manual/AR fallback and clearly label its measurement method.")
                            .multilineTextAlignment(.center).foregroundStyle(.secondary)
                    }.padding()
                }
            }
            .navigationTitle("Scan Room")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Finish scan") { stopRequested = true }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Show measurements") { showingResult = true }
                        .disabled(exportedJSON.isEmpty)
                }
            }
            .sheet(isPresented: $showingResult) {
                NavigationStack {
                    ScrollView { Text(exportedJSON).font(.system(.caption, design: .monospaced)).textSelection(.enabled).padding() }
                        .navigationTitle("Room scan result")
                        .toolbar {
                            ToolbarItem(placement: .topBarLeading) { ShareLink(item: exportedJSON) { Label("Export JSON", systemImage: "square.and.arrow.up") } }
                            ToolbarItem(placement: .topBarTrailing) { Button("Done") { showingResult = false } }
                        }
                }
            }
        }
    }

    @MainActor
    private func uploadMeasurements() async {
        guard let base = URL(string: serverBaseURL.trimmingCharacters(in: .whitespacesAndNewlines)),
              ["http", "https"].contains(base.scheme?.lowercased() ?? "") else {
            uploadStatus = "Enter a valid http:// or https:// backend URL."
            return
        }
        guard let jsonData = exportedJSON.data(using: .utf8),
              let room = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any],
              room["length_m"] is NSNumber, room["width_m"] is NSNumber, room["height_m"] is NSNumber else {
            uploadStatus = "Scan is missing valid room dimensions. Finish the scan and review the result."
            return
        }
        let payload: [String: Any] = ["sweep_id": sweepID.trimmingCharacters(in: .whitespacesAndNewlines), "room": room]
        guard let body = try? JSONSerialization.data(withJSONObject: payload) else {
            uploadStatus = "Could not encode the room measurement."
            return
        }
        var endpoint = base
        endpoint.append(path: "/api/sweep/room-measurement")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        uploading = true
        defer { uploading = false }
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse else { throw UploadError.invalidResponse }
            guard (200..<300).contains(http.statusCode) else {
                let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
                throw UploadError.server(detail ?? "Server returned HTTP \(http.statusCode). Confirm the sweep ID and backend URL.")
            }
            uploadStatus = "RoomPlan measurements attached to sweep \(sweepID). Return to the browser app and finalize the claim packet."
        } catch {
            uploadStatus = "Upload failed: \(error.localizedDescription). Ensure the phone can reach the backend and that the sweep is active."
        }
    }

    private enum UploadError: LocalizedError {
        case invalidResponse
        case server(String)
        var errorDescription: String? {
            switch self {
            case .invalidResponse: return "Invalid server response."
            case .server(let message): return message
            }
        }
    }
}

private struct RoomCaptureHost: UIViewRepresentable {
    @Binding var exportedJSON: String
    @Binding var stopRequested: Bool

    func makeCoordinator() -> Coordinator { Coordinator(exportedJSON: $exportedJSON) }

    func makeUIView(context: Context) -> RoomCaptureView {
        let view = RoomCaptureView(frame: .zero)
        view.delegate = context.coordinator
        view.captureSession.delegate = context.coordinator
        let config = RoomCaptureSession.Configuration()
        view.captureSession.run(configuration: config)
        return view
    }

    func updateUIView(_ uiView: RoomCaptureView, context: Context) {
        if stopRequested {
            uiView.captureSession.stop(pauseARSession: true)
            DispatchQueue.main.async { self.stopRequested = false }
        }
    }

    static func dismantleUIView(_ uiView: RoomCaptureView, coordinator: Coordinator) {
        uiView.captureSession.stop(pauseARSession: true)
    }

    final class Coordinator: NSObject, RoomCaptureViewDelegate, RoomCaptureSessionDelegate {
        @Binding var exportedJSON: String
        init(exportedJSON: Binding<String>) { _exportedJSON = exportedJSON }

        func captureView(shouldPresent roomDataForProcessing: CapturedRoom, error: Error?) -> Bool { true }

        func captureView(didPresent processedResult: CapturedRoom, error: Error?) {
            guard error == nil else { return }
            // RoomPlan dimensions are in metres. Group wall lengths by their horizontal
            // orientation to estimate the two principal room dimensions. Non-rectangular
            // geometry must be reviewed; we do not pretend a bounding box is exact area.
            let walls = processedResult.walls
            let wallHeights = walls.map { Double($0.dimensions.y) }.filter { $0 > 0 }
            let height = median(wallHeights)
            var orientationLengths: [Int: [Double]] = [0: [], 1: []]
            var orientationResiduals: [Double] = []
            for wall in walls {
                let x = Double(wall.transform.columns.0.x)
                let z = Double(wall.transform.columns.0.z)
                var angle = atan2(z, x)
                while angle < 0 { angle += Double.pi }
                while angle >= Double.pi { angle -= Double.pi }
                let axis = abs(angle) < Double.pi / 4 || abs(angle - Double.pi) < Double.pi / 4 ? 0 : 1
                let targetAngle = axis == 0 ? 0.0 : Double.pi / 2
                orientationResiduals.append(min(abs(angle - targetAngle), abs(Double.pi - angle - targetAngle)))
                let length = Double(wall.dimensions.x)
                if length > 0 { orientationLengths[axis, default: []].append(length) }
            }
            let axisA = median(orientationLengths[0] ?? [])
            let axisB = median(orientationLengths[1] ?? [])
            let dimensions = [axisA, axisB].filter { $0 > 0 }.sorted(by: >)
            let length = dimensions.first ?? 0
            let width = dimensions.count > 1 ? dimensions[1] : 0
            let floorAreas = processedResult.floors.map { abs(Double($0.dimensions.x * $0.dimensions.z)) }.filter { $0 > 0 }
            let floorArea = floorAreas.reduce(0, +)
            let grossWallArea = walls.reduce(0.0) { $0 + abs(Double($1.dimensions.x * $1.dimensions.y)) }
            func reasonablyPaired(_ values: [Double]) -> Bool {
                guard values.count >= 2 else { return false }
                let mean = values.reduce(0, +) / Double(values.count)
                guard mean > 0 else { return false }
                return (values.max()! - values.min()!) / mean <= 0.15
            }
            let rectangular = walls.count >= 4 && length > 0 && width > 0 && height > 0
                && reasonablyPaired(orientationLengths[0] ?? [])
                && reasonablyPaired(orientationLengths[1] ?? [])
                && orientationResiduals.allSatisfy { $0 <= Double.pi / 12 }
            let summary = RoomPlanSummary(
                length_m: length > 0 ? length : nil,
                width_m: width > 0 ? width : nil,
                height_m: height > 0 ? height : nil,
                floor_area_m2: rectangular ? (floorArea > 0 ? floorArea : length * width) : nil,
                wall_area_m2: grossWallArea > 0 ? grossWallArea : (rectangular ? 2 * (length + width) * height : nil),
                shelved_wall_area_m2: nil,
                shape: rectangular ? "roomplan_rectangular_approximation" : "roomplan_irregular_or_incomplete",
                scale_method: "Apple RoomPlan / ARKit metric room capture; verify against tape ground truth",
                confidence: rectangular ? 0.75 : 0.45,
                measurement_source: "Apple RoomPlan CapturedRoom",
                wall_count: walls.count,
                floor_surface_count: processedResult.floors.count
            )
            do {
                let encoder = JSONEncoder()
                encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
                let data = try encoder.encode(summary)
                DispatchQueue.main.async { self.exportedJSON = String(data: data, encoding: .utf8) ?? "" }
            } catch {
                DispatchQueue.main.async { self.exportedJSON = "Room scan export failed: \(error.localizedDescription)" }
            }
        }

        private func median(_ values: [Double]) -> Double {
            let sorted = values.filter { $0.isFinite && $0 > 0 }.sorted()
            guard !sorted.isEmpty else { return 0 }
            let middle = sorted.count / 2
            return sorted.count.isMultiple(of: 2) ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle]
        }
    }
}


private struct RoomPlanSummary: Codable {
    let length_m: Double?
    let width_m: Double?
    let height_m: Double?
    let floor_area_m2: Double?
    let wall_area_m2: Double?
    let shelved_wall_area_m2: Double?
    let shape: String
    let scale_method: String
    let confidence: Double
    let measurement_source: String
    let wall_count: Int
    let floor_surface_count: Int
}
