# RoomPlan native companion

This SwiftUI companion uses Apple's RoomPlan/ARKit on a supported iPhone/iPad to capture metric room geometry and attach it directly to an active Library Contents Claim Agent sweep.

## Build in Xcode

1. On macOS, install Xcode and XcodeGen (`brew install xcodegen`), then run `cd native_ios/RoomScan && xcodegen generate` to generate the Xcode project from the included `project.yml`.
2. Open `LibraryClaimRoomScan.xcodeproj`, select a RoomPlan-supported iPhone/iPad as the run target, and configure signing for your Apple developer team. The simulator is not a substitute for real room scanning.
3. Run on the physical device. RoomPlan requires camera permission and compatible hardware.

## Attach to a live sweep

1. Run the Python backend on the computer, listening on the LAN interface, e.g. `python -m uvicorn app:app --host 0.0.0.0 --port 4178`.
2. Open the browser app at `http://127.0.0.1:4178` on that computer and start the inventory sweep.
3. Copy the **Active Sweep ID** displayed in the browser. Find the computer's LAN IPv4 address and enter `http://<computer-lan-ip>:4178` in the iOS scanner.
4. Walk the room with RoomPlan, tap **Finish scan**, then tap **Send measurements to active sweep**. Enter the active sweep ID. A success status confirms the backend accepted it.
5. Return to the browser app and finalize the packet. Imported RoomPlan measurements take precedence over manual dimensions where the provider supplied a value.

Use a trusted network only. The local HTTP option is for a development LAN; use HTTPS and authentication before exposing this endpoint beyond a trusted network. The backend currently uses in-memory sweep sessions, so keep the backend process running until the packet is finalized.

## Measurement honesty / limits

- RoomPlan supplies metric geometry; it is not proof that every room dimension meets the assignment's error threshold. Validate against tape measurements and the provided evaluation CSV.
- Irregular or incomplete geometry intentionally leaves floor area blank rather than reporting a rectangular bounding-box estimate as exact. Gross wall area is a surface sum; verify openings and wall segmentation.
- Shelf-covered wall area is not automatically segmented by RoomPlan in this implementation. Enter/verify it from the sweep and retain the review flag.
- This native scanner sends room measurements into the same active backend sweep, but it does not replace the browser's live book camera/voice pipeline. It has not been compiled or device-tested in this Linux environment; finish the Xcode build and physical-device test before claiming that it passes.
