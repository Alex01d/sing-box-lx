# TASKS:149 — Embedded Tailscale AWG

**Фича:** [019](../../FEATURES/019-TAILSCALE_AWG/FEATURE.md).

## Реализовано

- [x] Typed optional profile, shared AWG validation/rendering/configure.
- [x] Per-device pre-Up hook и scoped cleanup/profile/carrier state.
- [x] AWG framing classifier для direct UDP и DERP, headroom8.
- [x] External auto/derp carrier и fail-closed outer outage.
- [x] Optional adapter/protobuf/libbox transport status без secret data.
- [x] Build capability и неполные tag combinations с явным отказом.
- [x] Pinned external bootstrap, minimal dependency/security patches.
- [x] Isolated direct/DERP, TCP/UDP, rekey/cookie/lifecycle/negative tooling.
- [x] Source synchronization и protobuf regeneration с incoming runtime memory.
- [x] Public-only reusable source/spec scope; private environments/logs excluded.

## До публикации релиза

- [ ] Immutable опубликованная revision patched Tailscale dependency в go.mod.
- [ ] Consumer CI и ручная desktop acceptance на поддерживаемых ОС.
- [ ] Windows/macOS route/DNS/underlay/reload/handoff fixes по результатам тестов.
- [ ] Android длительная DERP stability, mobile handoff и полная ABI/AAB приёмка.
- [ ] iOS Packet Tunnel/XCFramework/native bridge/signing/physical-device gate.
- [ ] Отдельное решение о peer relay и embedded SSH после security/compatibility.

Engineering source tests и bounded requests не закрывают перечисленные gates.
Сохранять неудачные cases; диагностический retry не заменяет исходный результат.
