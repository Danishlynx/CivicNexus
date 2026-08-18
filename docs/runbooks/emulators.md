# Runbook: local emulators for integration tests

The Firestore-backed case store tests skip unless an emulator is reachable.
Emulators run containerized (dev machine lacks Java 21+ — ADR-002 item 5).

```powershell
docker compose -f docker-compose.emulators.yaml up -d
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8087"
$env:PUBSUB_EMULATOR_HOST   = "127.0.0.1:8085"
uv run pytest libs/tools
```

Notes:
- Always pin explicit `127.0.0.1` host:ports. The Pub/Sub emulator binds IPv6
  `[::1]` by default, which breaks gRPC clients resolving `localhost` to IPv4
  on Windows.
- Emulator data is in-memory; restarting the containers wipes state.
- Tear down with `docker compose -f docker-compose.emulators.yaml down`.
