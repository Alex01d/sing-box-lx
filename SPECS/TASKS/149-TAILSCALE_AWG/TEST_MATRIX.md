# TEST MATRIX:149 — Embedded Tailscale AWG

**Фича:** [019](../../FEATURES/019-TAILSCALE_AWG/FEATURE.md).
Все адреса, профили и сервисы изолированного lab — synthetic fixtures.

| Область | Обязательная проверка | Критерий |
|---|---|---|
| Wire compatibility | plain/AWG2/AWG3 × direct/forced DERP × IPv4/IPv6 payload × два направления | TCP16MiB/checksum и UDP64/512/1200, actual peer path |
| Version3.1 | header protection, padding, random trailers, ranged timers | Совместимый независимый peer, canonical profile fingerprint |
| Framing | S padding/Geneve collision, широкие H ranges, STUN/DISCO, cookie/junk | Служебные signatures различимы, WG decoder аутентифицирует payload |
| Lifecycle | pre-Up apply, rekey, reload/restart, two endpoints, network replacement | Stable local identity, isolation, корректный cleanup |
| Security | Serve socket guards, DERP borrowed-read ACK Close/Open, race | RED/GREEN regression и явное условие снятия backport |
| Config | unknown fields, injection chars, invalid bounds/key/combination | Отказ до запуска, safe error без key/CPS |
| Capability | tag absent, invalid integration tag set, consumer unknown capability | Config failure или compile-time guard; no false capability/WG fallback |
| Carrier | auto UDP/XUDP и forced DERP TCP поверх VLESS | Native fallback отсутствует, explicit carrier выше ambient proxy |
| Routing | protected private HTTPS и выбранный public VLESS | Ожидаемый origin, сертификаты проверены |
| Failures | profile mismatch, ACL deny, logout, peer/outer outage | Private data/DNS не уходят в direct/public DNS/VLESS |
| DNS | case/trailing dot, short names, hosts-only suffix, longest forwarded suffix | Существующая семантика plain Tailscale сохранена |
| Status | unary/stream + libbox, mode/applied/fingerprint/error | Секреты отсутствуют; control login не считается data plane |
| Connection test | существующий StartConnectionTest, HTTP403/401 | Ответ приложения отделён от network failure |
| Regression | standalone WG/AWG и ordinary Tailscale | Shared codec wire output/validation не меняются |

## Linux / desktop

Изолированный lab работает в отдельных контейнерах/network с проверкой label и
route overlaps; не меняет host TUN/firewall/sysctl или OS CA store. Lab CA
доверяется только test processes. Ручной launcher/TUN сценарий отдельно
проверяет import/edit/export, optional auth key/browser login, protected rules
до login/после logout, reload identity, sleep/network handoff и остановку.

## Android

Один VPN service, protected underlay sockets, per-node identity. Проверять
same-signer in-place update, consent revoke, UI/background/restart, Wi-Fi/mobile
handoff, direct/DERP TCP/UDP и отрицательные desktop cases. Не удалять user data
ради установки; diagnostic APK/source instrumentation отделять от clean build.
Длительные DERP timeouts остаются отдельным открытым acceptance gate; успех
source hotfix regression не доказывает причину каждого сетевого timeout.

## Остальные платформы

Windows/macOS: platform build + native route/DNS/underlay/reload/network change
на устройстве; дополнительные fixes оформляются в той же feature. iOS:
настоящий Packet Tunnel/native bridge/XCFramework/App Group/Keychain/signing и
проверка на физическом устройстве. Scaffold не закрывает gate.

## Воспроизводимость и evidence

Точные pins/patch hashes — lx-test/tailscale-awg/dependencies.json. Сохранять
commands/toolchains/source+artifact hashes и фактически пройденные scenarios во
внешнем test workspace. Test error/harness error/untested не переименовывать в
PASS. Полный suite — CI; локально только профильные named tests и нужные builds.
Личные profiles, identities, topology и field logs в исходники не включаются.
